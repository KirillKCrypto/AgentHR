"""Сохранение вакансий и резюме, профиль знаний и gap-анализ.

Слой отвечает за запись в БД и вычисления поверх онтологии; LLM используется
для извлечения навыков (`app/services/analysis.py`) и, best-effort, для ревью
новых тем (`app/services/ontology_auto_review.py`). Любой навык получает
тему: если совпадения нет, `app.services.topics` создаёт provisional-тему и
запись в очереди ревью. Поэтому новые навыки не остаются с `topic_id = NULL`.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings.base import EmbeddingProvider
from app.llm.base import LLMProvider
from app.models import (
    Resume,
    ResumeSkill,
    Topic,
    UserSkillState,
    Vacancy,
    VacancySkill,
)
from app.services.analysis import (
    ExtractedSkill,
    ResumeProfile,
    VacancyRequirements,
    extract_resume_skills,
    extract_vacancy_requirements,
)
from app.services.normalization import TopicMatch, normalize_name
from app.services.ontology_auto_review import run_auto_review
from app.services.topics import (
    create_skill_matcher,
    load_topic_index,
    resolve_or_create_topics,
)

# Вес источника оценки: чем надёжнее источник, тем сильнее он влияет на профиль.
# Резюме — самый слабый источник: кандидат описывает себя сам.
SOURCE_WEIGHTS: dict[str, float] = {
    "manual": 1.0,
    "interview": 0.9,
    "assessment": 0.8,
    "resume": 0.6,
}

# Потолок уверенности: даже много согласованных свидетельств не дают 100%
MAX_CONFIDENCE = 0.95
# Сколько последних свидетельств хранить в профиле
MAX_EVIDENCE = 10


class NotFoundError(Exception):
    """Запрошенный объект не найден или принадлежит другому пользователю."""


@dataclass(frozen=True)
class TopicBriefData:
    """Краткое описание темы для ответов API и инструментов."""

    id: uuid.UUID
    key: str
    name: str
    category: str | None = None
    status: str = "canonical"


@dataclass(frozen=True)
class SkillEntry:
    """Навык документа вместе с сопоставленной темой."""

    id: uuid.UUID
    raw_name: str
    level: int
    weight: float | None
    confidence: float
    evidence: str | None
    match_method: str
    topic: TopicBriefData | None = None
    requirement_group: str | None = None
    requirement_logic: str = "SINGLE"
    criticality: str = "must_have"


@dataclass(frozen=True)
class ProfileTopic:
    """Тема в срезе профиля знаний."""

    topic_id: uuid.UUID
    topic_key: str
    topic_name: str
    category: str | None
    proficiency: int
    confidence: float
    source: str
    last_assessed: datetime | None
    status: str = "canonical"


@dataclass(frozen=True)
class UnmatchedSkill:
    """Навык из резюме, которому не нашлось темы в онтологии."""

    raw_name: str
    level: int
    confidence: float
    evidence: str | None
    match_method: str


@dataclass(frozen=True)
class ProfileSnapshot:
    """Срез профиля знаний пользователя."""

    user_id: uuid.UUID
    topics: tuple[ProfileTopic, ...] = ()
    unmatched_skills: tuple[UnmatchedSkill, ...] = ()


@dataclass(frozen=True)
class GapItem:
    """Разрыв между требуемым и текущим уровнем по одному навыку."""

    skill_name: str
    required_level: int
    user_level: int
    gap: int
    satisfied: bool
    weight: float
    topic_key: str | None = None
    topic_name: str | None = None
    topic_status: str | None = None
    requirement_group: str | None = None
    requirement_logic: str = "SINGLE"
    criticality: str = "must_have"


@dataclass(frozen=True)
class GapReport:
    """Gap-анализ вакансии относительно профиля пользователя."""

    vacancy_id: uuid.UUID
    vacancy_title: str | None
    items: tuple[GapItem, ...] = ()
    overall_readiness: float = 0.0
    coverage_all: float = 0.0
    confirmed_readiness: float | None = None
    provisional_count: int = 0
    provisional_weight: float = 0.0
    confirmed_weight: float = 0.0
    critical_count: int = 0
    critical_weight: float = 0.0
    critical_gap_count: int = 0
    unmatched_count: int = 0


def weighted_estimate(entries: list[tuple[int, float]]) -> tuple[int, float]:
    """Взвешенная оценка уровня по нескольким свидетельствам.

    Уровень — среднее, взвешенное уверенностью; уверенность агрегата растёт
    по формуле независимых свидетельств `1 - Π(1 - c_i)` и ограничена
    `MAX_CONFIDENCE`.
    """
    usable = [(level, confidence) for level, confidence in entries if confidence > 0]
    if not usable:
        return 0, 0.0

    total_weight = sum(confidence for _, confidence in usable)
    level = round(sum(level * confidence for level, confidence in usable) / total_weight)
    survival = 1.0
    for _, confidence in usable:
        survival *= 1.0 - confidence

    return _clamp_level(level), round(min(MAX_CONFIDENCE, 1.0 - survival), 3)


async def analyze_vacancy(
    session: AsyncSession,
    provider: LLMProvider,
    user_id: uuid.UUID,
    *,
    raw_text: str,
    title: str | None = None,
    company: str | None = None,
    embedder: EmbeddingProvider | None = None,
) -> Vacancy:
    """Создаёт вакансию и сохраняет извлечённые из неё навыки."""
    requirements = await extract_vacancy_requirements(provider, raw_text)
    return await save_vacancy_analysis(
        session,
        user_id,
        raw_text=raw_text,
        requirements=requirements,
        title=title,
        company=company,
        provider=provider,
        embedder=embedder,
    )


async def save_vacancy_analysis(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    raw_text: str,
    requirements: VacancyRequirements,
    title: str | None = None,
    company: str | None = None,
    provider: LLMProvider | None = None,
    embedder: EmbeddingProvider | None = None,
) -> Vacancy:
    """Сохраняет вакансию вместе с уже извлечёнными требованиями."""
    vacancy = Vacancy(
        user_id=user_id,
        title=_clean(title) or requirements.title,
        company=_clean(company) or requirements.company,
        raw_text=raw_text,
    )
    session.add(vacancy)
    await session.flush()

    skills = _unique_skills(requirements.skills)
    matches = await _match_skills(session, skills, embedder)
    matches = await resolve_or_create_topics(
        session,
        [(skill.name, skill.evidence) for skill in skills],
        matches,
        source_type="vacancy",
        source_id=vacancy.id,
    )
    new_topic_ids = [match.topic_id for match in matches if match.method == "provisional"]

    for skill, match in zip(skills, matches, strict=True):
        session.add(
            VacancySkill(
                vacancy_id=vacancy.id,
                topic_id=match.topic_id,
                raw_name=_truncate(skill.name, 200),
                required_level=skill.level,
                weight=skill.weight,
                requirement_group=skill.group,
                requirement_logic=skill.logic,
                criticality=skill.criticality,
                confidence=skill.confidence,
                evidence=skill.evidence,
                match_method=match.method,
            )
        )

    await session.commit()
    await session.refresh(vacancy)

    # Автопроверка новых тем: best-effort, ошибка не должна ломать загрузку.
    await run_auto_review(
        session,
        new_topic_ids,
        provider=provider,
        embedder=embedder,
    )
    return vacancy


async def analyze_resume(
    session: AsyncSession,
    provider: LLMProvider,
    user_id: uuid.UUID,
    *,
    raw_text: str,
    title: str | None = None,
    embedder: EmbeddingProvider | None = None,
) -> Resume:
    """Создаёт резюме, сохраняет навыки и пересобирает профиль знаний."""
    profile: ResumeProfile = await extract_resume_skills(provider, raw_text)
    return await save_resume_analysis(
        session,
        user_id,
        raw_text=raw_text,
        profile=profile,
        title=title,
        provider=provider,
        embedder=embedder,
    )


async def save_resume_analysis(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    raw_text: str,
    profile: ResumeProfile,
    title: str | None = None,
    provider: LLMProvider | None = None,
    embedder: EmbeddingProvider | None = None,
) -> Resume:
    """Сохраняет резюме с уже извлечёнными навыками и обновляет профиль."""
    resume = Resume(user_id=user_id, title=_clean(title), raw_text=raw_text)
    session.add(resume)
    await session.flush()

    skills = _unique_skills(profile.skills)
    matches = await _match_skills(session, skills, embedder)
    matches = await resolve_or_create_topics(
        session,
        [(skill.name, skill.evidence) for skill in skills],
        matches,
        source_type="resume",
        source_id=resume.id,
    )
    new_topic_ids = [match.topic_id for match in matches if match.method == "provisional"]

    for skill, match in zip(skills, matches, strict=True):
        session.add(
            ResumeSkill(
                resume_id=resume.id,
                topic_id=match.topic_id,
                raw_name=_truncate(skill.name, 200),
                proficiency=skill.level,
                confidence=skill.confidence,
                evidence=skill.evidence,
                match_method=match.method,
            )
        )

    await session.commit()
    await session.refresh(resume)

    # Автопроверка идёт до rebuild_profile: профиль должен пересчитаться уже
    # с учётом merge/approve, иначе срез останется на старой теме.
    await run_auto_review(
        session,
        new_topic_ids,
        provider=provider,
        embedder=embedder,
    )

    await rebuild_profile(session, user_id)
    return resume


async def rebuild_profile(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> ProfileSnapshot:
    """Пересчитывает профиль знаний по всем резюме пользователя.

    Более сильные источники (`interview`, `manual`, `assessment`) не
    перезаписываются: пересчёт по резюме не должен снижать оценку, полученную
    на собеседовании. Свидетельства из резюме объединяются взвешенно.
    """
    rows = (
        await session.execute(
            select(ResumeSkill, Resume.id)
            .join(Resume, Resume.id == ResumeSkill.resume_id)
            .where(Resume.user_id == user_id, ResumeSkill.topic_id.is_not(None))
            .order_by(Resume.created_at, ResumeSkill.created_at)
        )
    ).all()

    grouped: dict[uuid.UUID, list[tuple[ResumeSkill, uuid.UUID]]] = {}
    for skill, resume_id in rows:
        assert skill.topic_id is not None  # отфильтровано в запросе
        grouped.setdefault(skill.topic_id, []).append((skill, resume_id))

    states = {
        state.topic_id: state
        for state in (
            await session.scalars(select(UserSkillState).where(UserSkillState.user_id == user_id))
        ).all()
    }
    assessed_at = now or datetime.now(UTC)

    for topic_id, entries in grouped.items():
        state = states.get(topic_id)
        if state is not None and state.source != "resume":
            continue

        level, confidence = weighted_estimate(
            [(skill.proficiency, skill.confidence) for skill, _ in entries]
        )
        evidence = [
            {
                "type": "resume",
                "id": str(resume_id),
                "text": skill.evidence,
                "confidence": skill.confidence,
            }
            for skill, resume_id in entries
        ][-MAX_EVIDENCE:]

        if state is None:
            state = UserSkillState(user_id=user_id, topic_id=topic_id)
            session.add(state)

        state.proficiency = level
        state.confidence = confidence
        state.source = "resume"
        state.evidence = evidence
        state.last_assessed = assessed_at

    # Резюме удалили или навык перестал быть релевантным — убираем срез,
    # если он был построен только по резюме.
    for topic_id, state in states.items():
        if state.source == "resume" and topic_id not in grouped:
            await session.delete(state)

    await session.commit()
    return await get_profile(session, user_id)


async def get_profile(session: AsyncSession, user_id: uuid.UUID) -> ProfileSnapshot:
    """Возвращает срез профиля знаний пользователя."""
    rows = (
        await session.execute(
            select(UserSkillState, Topic)
            .join(Topic, Topic.id == UserSkillState.topic_id)
            .where(
                UserSkillState.user_id == user_id,
                Topic.status.in_(("canonical", "provisional")),
            )
            .order_by(Topic.key)
        )
    ).all()

    topics = tuple(
        ProfileTopic(
            topic_id=topic.id,
            topic_key=topic.key,
            topic_name=topic.name,
            category=topic.category,
            proficiency=state.proficiency,
            confidence=state.confidence,
            source=state.source,
            last_assessed=state.last_assessed,
            status=topic.status,
        )
        for state, topic in rows
    )

    return ProfileSnapshot(
        user_id=user_id,
        topics=topics,
        unmatched_skills=await _unmatched_resume_skills(session, user_id),
    )


async def compute_gaps(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy_id: uuid.UUID,
) -> GapReport:
    """Считает разрывы между требованиями вакансии и профилем пользователя.

    Готовность считается только по навыкам, сопоставленным с онтологией:
    для навыков вне словаря нет достоверной оценки уровня, поэтому они
    показываются в разрывах, но не искажают общий процент.
    """
    vacancy = await get_vacancy(session, user_id, vacancy_id)

    skills = (
        await session.scalars(
            select(VacancySkill)
            .where(VacancySkill.vacancy_id == vacancy.id)
            .order_by(VacancySkill.weight.desc(), VacancySkill.raw_name)
        )
    ).all()
    topics = {topic.id: topic for topic in (await session.scalars(select(Topic))).all()}
    states = {
        state.topic_id: state
        for state in (
            await session.scalars(select(UserSkillState).where(UserSkillState.user_id == user_id))
        ).all()
    }

    items: list[GapItem] = []
    calculations: list[tuple[VacancySkill, GapItem, float, str | None]] = []
    provisional_count = 0
    provisional_weight = 0.0
    critical_count = 0
    critical_weight = 0.0
    critical_gap_count = 0
    unmatched_count = 0

    for skill in skills:
        topic = topics.get(skill.topic_id) if skill.topic_id is not None else None
        state = states.get(skill.topic_id) if skill.topic_id is not None else None
        user_level = state.proficiency if state is not None else 0
        gap = max(0, skill.required_level - user_level)
        topic_status = topic.status if topic is not None else None
        logic = skill.requirement_logic or "SINGLE"
        criticality = skill.criticality or "must_have"
        if criticality == "must_have":
            critical_count += 1
            critical_weight += skill.weight
            if gap > 0:
                critical_gap_count += 1

        item = GapItem(
            skill_name=skill.raw_name,
            required_level=skill.required_level,
            user_level=user_level,
            gap=gap,
            satisfied=gap == 0,
            weight=skill.weight,
            topic_key=topic.key if topic is not None else None,
            topic_name=topic.name if topic is not None else None,
            topic_status=topic_status,
            requirement_group=skill.requirement_group,
            requirement_logic=logic,
            criticality=criticality,
        )
        items.append(item)

        if topic is None or topic_status not in ("canonical", "provisional"):
            unmatched_count += 1
            calculations.append((skill, item, 0.0, topic_status))
            continue

        ratio = 1.0 if skill.required_level <= 0 else min(1.0, user_level / skill.required_level)
        calculations.append((skill, item, ratio, topic_status))
        if topic_status == "provisional":
            provisional_count += 1
            provisional_weight += skill.weight

    grouped: dict[str, list[tuple[VacancySkill, GapItem, float, str | None]]] = {}
    for calculation in calculations:
        skill = calculation[0]
        logic = skill.requirement_logic or "SINGLE"
        if skill.requirement_group and logic in ("AND", "OR"):
            key = f"group:{skill.requirement_group}"
        else:
            key = f"skill:{skill.id}"
        grouped.setdefault(key, []).append(calculation)

    weighted_all_done = 0.0
    weighted_all_total = 0.0
    weighted_confirmed_done = 0.0
    confirmed_weight = 0.0

    for group in grouped.values():
        logic = group[0][0].requirement_logic or "SINGLE"
        ratios = [ratio for _, _, ratio, _ in group]
        weights = [item.weight for _, item, _, _ in group]
        if logic == "OR":
            group_ratio = max(ratios)
            group_weight = max(weights)
        elif logic == "AND":
            group_ratio = min(ratios)
            group_weight = sum(weights)
        else:
            group_ratio = ratios[0]
            group_weight = weights[0]

        weighted_all_done += group_weight * group_ratio
        weighted_all_total += group_weight

        if all(topic_status == "canonical" for _, _, _, topic_status in group):
            weighted_confirmed_done += group_weight * group_ratio
            confirmed_weight += group_weight

    if weighted_all_total > 0:
        coverage_all = weighted_all_done / weighted_all_total
    else:
        # Навыков вне онтологии нет, а требований нет вовсе — покрытие полное
        coverage_all = 1.0 if not skills else 0.0

    confirmed_readiness = (
        round(weighted_confirmed_done / confirmed_weight, 3) if confirmed_weight > 0 else None
    )

    return GapReport(
        vacancy_id=vacancy.id,
        vacancy_title=vacancy.title,
        items=tuple(items),
        overall_readiness=round(coverage_all, 3),
        coverage_all=round(coverage_all, 3),
        confirmed_readiness=confirmed_readiness,
        provisional_count=provisional_count,
        provisional_weight=round(provisional_weight, 3),
        confirmed_weight=round(confirmed_weight, 3),
        critical_count=critical_count,
        critical_weight=round(critical_weight, 3),
        critical_gap_count=critical_gap_count,
        unmatched_count=unmatched_count,
    )


async def get_vacancy(session: AsyncSession, user_id: uuid.UUID, vacancy_id: uuid.UUID) -> Vacancy:
    """Вакансия пользователя или `NotFoundError` (изоляция по владельцу)."""
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.user_id != user_id:
        raise NotFoundError("Вакансия не найдена")
    return vacancy


async def get_resume(session: AsyncSession, user_id: uuid.UUID, resume_id: uuid.UUID) -> Resume:
    """Резюме пользователя или `NotFoundError` (изоляция по владельцу)."""
    resume = await session.get(Resume, resume_id)
    if resume is None or resume.user_id != user_id:
        raise NotFoundError("Резюме не найдено")
    return resume


async def load_vacancy_skills(
    session: AsyncSession, vacancy_id: uuid.UUID
) -> tuple[SkillEntry, ...]:
    """Навыки вакансии вместе с темами онтологии."""
    rows = (
        await session.execute(
            select(VacancySkill, Topic)
            .outerjoin(Topic, Topic.id == VacancySkill.topic_id)
            .where(VacancySkill.vacancy_id == vacancy_id)
            .order_by(VacancySkill.required_level.desc(), VacancySkill.raw_name)
        )
    ).all()
    return tuple(
        SkillEntry(
            id=skill.id,
            raw_name=skill.raw_name,
            level=skill.required_level,
            weight=skill.weight,
            confidence=skill.confidence,
            evidence=skill.evidence,
            match_method=skill.match_method,
            topic=_topic_brief(topic),
            requirement_group=skill.requirement_group,
            requirement_logic=skill.requirement_logic,
            criticality=skill.criticality,
        )
        for skill, topic in rows
    )


async def load_resume_skills(session: AsyncSession, resume_id: uuid.UUID) -> tuple[SkillEntry, ...]:
    """Навыки резюме вместе с темами онтологии."""
    rows = (
        await session.execute(
            select(ResumeSkill, Topic)
            .outerjoin(Topic, Topic.id == ResumeSkill.topic_id)
            .where(ResumeSkill.resume_id == resume_id)
            .order_by(ResumeSkill.proficiency.desc(), ResumeSkill.raw_name)
        )
    ).all()
    return tuple(
        SkillEntry(
            id=skill.id,
            raw_name=skill.raw_name,
            level=skill.proficiency,
            weight=None,
            confidence=skill.confidence,
            evidence=skill.evidence,
            match_method=skill.match_method,
            topic=_topic_brief(topic),
        )
        for skill, topic in rows
    )


async def update_skill_proficiency(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    topic_key: str,
    score: int,
    evidence: str | None = None,
    source: str = "manual",
) -> ProfileTopic:
    """Обновляет оценку темы в профиле (ручное свидетельство или интервью).

    Новая оценка объединяется с текущей взвешенно по весу источника;
    свидетельства накапливаются, но не разрастаются бесконечно.
    """
    topic = await session.scalar(select(Topic).where(Topic.key == topic_key))
    if topic is None:
        raise NotFoundError(f"Тема {topic_key!r} не найдена")

    state = await session.scalar(
        select(UserSkillState).where(
            UserSkillState.user_id == user_id,
            UserSkillState.topic_id == topic.id,
        )
    )
    level = _clamp_level(score)
    confidence = SOURCE_WEIGHTS.get(source, 0.5)

    if state is None:
        state = UserSkillState(user_id=user_id, topic_id=topic.id)
        session.add(state)
        state.proficiency = level
        state.confidence = min(MAX_CONFIDENCE, confidence)
        state.evidence = []
    else:
        previous_weight = SOURCE_WEIGHTS.get(state.source, 0.5) * state.confidence
        new_weight = confidence
        total_weight = previous_weight + new_weight
        if total_weight > 0:
            state.proficiency = _clamp_level(
                round((state.proficiency * previous_weight + level * new_weight) / total_weight)
            )
        state.confidence = round(
            min(MAX_CONFIDENCE, 1.0 - (1.0 - state.confidence) * (1.0 - confidence)), 3
        )

    state.source = source
    state.last_assessed = datetime.now(UTC)
    state.evidence = [
        *(state.evidence or []),
        {"type": source, "text": evidence, "score": level},
    ][-MAX_EVIDENCE:]

    await session.commit()
    await session.refresh(state)

    return ProfileTopic(
        topic_id=topic.id,
        topic_key=topic.key,
        topic_name=topic.name,
        category=topic.category,
        proficiency=state.proficiency,
        confidence=state.confidence,
        source=state.source,
        last_assessed=state.last_assessed,
    )


async def _match_skills(
    session: AsyncSession,
    skills: list[ExtractedSkill],
    embedder: EmbeddingProvider | None,
) -> list[TopicMatch]:
    """Сопоставляет навыки с темами онтологии из БД."""
    if not skills:
        return []
    index = await load_topic_index(session)
    matcher = create_skill_matcher(index, embedder)
    return await matcher.match_many([skill.name for skill in skills])


async def _unmatched_resume_skills(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[UnmatchedSkill, ...]:
    """Навыки резюме вне онтологии: по одному на название, с лучшей оценкой."""
    skills = (
        await session.scalars(
            select(ResumeSkill)
            .join(Resume, Resume.id == ResumeSkill.resume_id)
            .where(Resume.user_id == user_id, ResumeSkill.topic_id.is_(None))
            .order_by(ResumeSkill.created_at)
        )
    ).all()

    best: dict[str, UnmatchedSkill] = {}
    for skill in skills:
        key = normalize_name(skill.raw_name)
        if not key:
            continue
        current = best.get(key)
        if current is None or skill.proficiency > current.level:
            best[key] = UnmatchedSkill(
                raw_name=skill.raw_name,
                level=skill.proficiency,
                confidence=skill.confidence,
                evidence=skill.evidence,
                match_method=skill.match_method,
            )
    return tuple(best.values())


def _topic_brief(topic: Topic | None) -> TopicBriefData | None:
    """Краткое описание темы или None для навыка вне онтологии."""
    if topic is None:
        return None
    return TopicBriefData(
        id=topic.id,
        key=topic.key,
        name=topic.name,
        category=topic.category,
        status=topic.status,
    )


def _unique_skills(skills: tuple[ExtractedSkill, ...]) -> list[ExtractedSkill]:
    """Убирает повторы навыков по нормализованному названию."""
    seen: set[str] = set()
    result: list[ExtractedSkill] = []
    for skill in skills:
        key = normalize_name(skill.name)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(skill)
    return result


def _clamp_level(value: Any) -> int:
    """Обрезает уровень в диапазон 0..100."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return 0
    return max(0, min(100, round(value)))


def _clean(value: str | None) -> str | None:
    """Строка без пустых хвостов; пустые значения — None."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _truncate(value: str, limit: int) -> str:
    """Обрезает строку до длины колонки."""
    return value[:limit]
