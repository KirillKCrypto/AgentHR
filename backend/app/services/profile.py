"""Сохранение вакансий и резюме, профиль знаний и gap-анализ.

Слой отвечает за запись в БД и вычисления поверх онтологии; LLM используется
для извлечения навыков (`app/services/analysis.py`) и, best-effort, для ревью
новых тем (`app/services/ontology_auto_review.py`). Любой навык получает
тему: если совпадения нет, `app.services.topics` создаёт provisional-тему и
запись в очереди ревью. Поэтому новые навыки не остаются с `topic_id = NULL`.
"""

import re
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings.base import EmbeddingProvider
from app.llm.base import LLMProvider
from app.models import (
    LearningPlan,
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
from app.services.content_hash import content_hash
from app.services.errors import NotFoundError
from app.services.learning_topics import NON_LEARNING_TOPIC_KEYS
from app.services.normalization import (
    DEFAULT_FUZZY_THRESHOLD,
    TopicIndex,
    TopicMatch,
    normalize_name,
)
from app.services.ontology_auto_review import run_auto_review
from app.services.topics import (
    create_skill_matcher,
    load_topic_index,
    resolve_or_create_topics,
)
from app.services.vacancy_level import resolve_vacancy_level

# Вес источника оценки: чем надёжнее источник, тем сильнее он влияет на профиль.
# Резюме — самый слабый источник: кандидат описывает себя сам.
SOURCE_WEIGHTS: dict[str, float] = {
    "manual": 1.0,
    "interview": 0.9,
    "test": 0.85,
    "resume": 0.6,
}

# Потолок уверенности: даже много согласованных свидетельств не дают 100%
MAX_CONFIDENCE = 0.95
# Сколько последних свидетельств хранить в профиле
MAX_EVIDENCE = 10

# Составные названия: «LightGBM/XGBoost», «Python, SQL», «Docker и Kubernetes».
_COMPOSITE_SPLIT_RE = re.compile(r"\s*(?:/|;|\||,|&|\s+и\s+)\s*", re.IGNORECASE)


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
    confidence: float = 0.5
    source: str = "resume"
    evidence_type: str = "self_report"
    verified_level: int | None = None
    review_due_at: datetime | None = None
    review_interval_days: int = 1
    last_assessed: datetime | None = None
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
    """Создаёт вакансию и сохраняет извлечённые из неё навыки.

    Тот же текст вакансии у того же пользователя возвращает уже сохранённую
    вакансию: повторная проверка не создаёт дубль и не вызывает LLM.
    """
    existing = await find_vacancy_by_text(session, user_id, raw_text)
    if existing is not None:
        return existing
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


async def find_vacancy_by_text(
    session: AsyncSession, user_id: uuid.UUID, raw_text: str
) -> Vacancy | None:
    """Вакансия пользователя с тем же нормализованным текстом."""
    return await session.scalar(
        select(Vacancy)
        .where(
            Vacancy.user_id == user_id,
            Vacancy.content_hash == content_hash(raw_text),
        )
        .order_by(Vacancy.created_at)
        .limit(1)
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
    resolved_title = _clean(title) or requirements.title
    vacancy = Vacancy(
        user_id=user_id,
        title=resolved_title,
        company=_clean(company) or requirements.company,
        level=resolve_vacancy_level(requirements.level, resolved_title, raw_text),
        raw_text=raw_text,
        content_hash=content_hash(raw_text),
    )
    session.add(vacancy)
    await session.flush()

    skills, matches = await _prepare_skills(
        session, _unique_skills(requirements.skills), embedder
    )
    matches = await resolve_or_create_topics(
        session,
        [(skill.name, skill.evidence) for skill in skills],
        matches,
        source_type="vacancy",
        source_id=vacancy.id,
    )
    skills, matches = _merge_skills_by_topic(skills, matches)
    touched_topic_ids = [match.topic_id for match in matches]

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
        touched_topic_ids,
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
    """Создаёт резюме, сохраняет навыки и пересобирает профиль знаний.

    Повторная загрузка того же текста возвращает существующее резюме и делает
    его активным. Профиль строится только по активному резюме.
    """
    existing = await find_resume_by_text(session, user_id, raw_text)
    if existing is not None:
        await activate_resume(session, user_id, existing.id, title=title)
        return existing
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


async def find_resume_by_text(
    session: AsyncSession, user_id: uuid.UUID, raw_text: str
) -> Resume | None:
    """Резюме пользователя с тем же нормализованным текстом."""
    return await session.scalar(
        select(Resume)
        .where(
            Resume.user_id == user_id,
            Resume.content_hash == content_hash(raw_text),
        )
        .order_by(Resume.created_at)
        .limit(1)
    )


async def activate_resume(
    session: AsyncSession,
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
    *,
    title: str | None = None,
) -> Resume:
    """Делает резюме активным и пересобирает профиль."""
    resume = await get_resume(session, user_id, resume_id)
    if title and not resume.title:
        resume.title = _clean(title)
    await session.execute(
        update(Resume)
        .where(Resume.user_id == user_id, Resume.id != resume_id)
        .values(is_active=False)
    )
    resume.is_active = True
    await session.commit()
    await rebuild_profile(session, user_id)
    await session.refresh(resume)
    return resume


async def delete_resume(
    session: AsyncSession,
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
) -> None:
    """Удаляет резюме; активным становится следующее по дате."""
    resume = await get_resume(session, user_id, resume_id)
    was_active = resume.is_active
    await session.delete(resume)
    await session.flush()

    if was_active:
        next_resume = await session.scalar(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
            .limit(1)
        )
        if next_resume is not None:
            next_resume.is_active = True
    await session.commit()
    await rebuild_profile(session, user_id)


async def clear_resumes(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Удаляет все резюме пользователя; ручные оценки и интервью сохраняются."""
    resumes = (await session.scalars(select(Resume).where(Resume.user_id == user_id))).all()
    for resume in resumes:
        await session.delete(resume)
    await session.commit()
    await rebuild_profile(session, user_id)


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
    await session.execute(
        update(Resume).where(Resume.user_id == user_id).values(is_active=False)
    )
    resume = Resume(
        user_id=user_id,
        title=_clean(title),
        raw_text=raw_text,
        content_hash=content_hash(raw_text),
        is_active=True,
    )
    session.add(resume)
    await session.flush()

    skills, matches = await _prepare_skills(session, _unique_skills(profile.skills), embedder)
    matches = await resolve_or_create_topics(
        session,
        [(skill.name, skill.evidence) for skill in skills],
        matches,
        source_type="resume",
        source_id=resume.id,
    )
    skills, matches = _merge_skills_by_topic(skills, matches)
    touched_topic_ids = [match.topic_id for match in matches]

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
        touched_topic_ids,
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
    """Пересчитывает профиль знаний по активному резюме пользователя.

    Более сильные источники (`interview`, `manual`) не
    перезаписываются: пересчёт по резюме не должен снижать оценку, полученную
    на собеседовании. Свидетельства из активного резюме объединяются взвешенно.
    """
    rows = (
        await session.execute(
            select(ResumeSkill, Resume.id)
            .join(Resume, Resume.id == ResumeSkill.resume_id)
            .where(
                Resume.user_id == user_id,
                Resume.is_active.is_(True),
                ResumeSkill.topic_id.is_not(None),
            )
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
    await _refresh_active_plans(session, user_id)
    return await get_profile(session, user_id)


async def _refresh_active_plans(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Пересобирает активные планы после смены активного резюме."""
    from app.services.plans import PlanError, create_plan

    plans = (
        await session.scalars(
            select(LearningPlan).where(
                LearningPlan.user_id == user_id,
                LearningPlan.status == "active",
            )
        )
    ).all()
    specs = [(plan.id, plan.vacancy_id) for plan in plans]
    for plan_id, vacancy_id in specs:
        try:
            await create_plan(session, user_id, vacancy_id=vacancy_id)
        except PlanError:
            await session.execute(
                update(LearningPlan)
                .where(LearningPlan.id == plan_id)
                .values(status="archived")
            )
            await session.commit()


async def get_profile(session: AsyncSession, user_id: uuid.UUID) -> ProfileSnapshot:
    """Возвращает срез профиля знаний пользователя."""
    rows = (
        await session.execute(
            select(UserSkillState, Topic)
            .join(Topic, Topic.id == UserSkillState.topic_id)
            .where(
                UserSkillState.user_id == user_id,
                Topic.status.in_(("canonical", "provisional")),
                Topic.key.not_in(NON_LEARNING_TOPIC_KEYS),
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
            evidence_type=state.evidence_type,
            verified_level=state.verified_level,
            review_due_at=state.review_due_at,
            review_interval_days=state.review_interval_days,
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


async def _prepare_skills(
    session: AsyncSession,
    skills: list[ExtractedSkill],
    embedder: EmbeddingProvider | None,
) -> tuple[list[ExtractedSkill], list[TopicMatch]]:
    """Расширяет составные названия и сопоставляет навыки с темами."""
    if not skills:
        return [], []
    index = await load_topic_index(session)
    expanded = _expand_composite_skills(skills, index)
    matcher = create_skill_matcher(index, embedder)
    matches = await matcher.match_many([skill.name for skill in expanded])
    return expanded, matches


async def _unmatched_resume_skills(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[UnmatchedSkill, ...]:
    """Навыки резюме вне онтологии: по одному на название, с лучшей оценкой."""
    skills = (
        await session.scalars(
            select(ResumeSkill)
            .join(Resume, Resume.id == ResumeSkill.resume_id)
            .where(
                Resume.user_id == user_id,
                Resume.is_active.is_(True),
                ResumeSkill.topic_id.is_(None),
            )
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


def _expand_composite_skills(
    skills: list[ExtractedSkill],
    index: TopicIndex,
) -> list[ExtractedSkill]:
    """Разбивает составные названия, если части по отдельности есть в онтологии."""
    expanded: list[ExtractedSkill] = []
    for skill in skills:
        # Точное название темы не трогаем, даже если внутри есть разделитель.
        if index.find_exact(skill.name) is not None:
            expanded.append(skill)
            continue
        parts = [
            part.strip()
            for part in _COMPOSITE_SPLIT_RE.split(skill.name)
            if part.strip() and len(part.strip()) >= 2
        ]
        matched = [part for part in parts if _has_topic(index, part)]
        # Составное название важнее случайного алиаса «lightgbm xgboost».
        if len(matched) >= 2 and len(matched) == len(parts):
            expanded.extend(replace(skill, name=part) for part in matched)
        elif _has_topic(index, skill.name):
            expanded.append(skill)
        else:
            expanded.append(skill)
    return _unique_skills(tuple(expanded))


def _has_topic(index: TopicIndex, name: str) -> bool:
    """Есть ли у названия точное, алиасное или нечёткое совпадение с темой."""
    if index.find_exact(name) is not None or index.find_alias(name) is not None:
        return True
    topic, _ = index.find_fuzzy(name, DEFAULT_FUZZY_THRESHOLD)
    return topic is not None


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


def _merge_skills_by_topic(
    skills: list[ExtractedSkill],
    matches: list[TopicMatch],
) -> tuple[list[ExtractedSkill], list[TopicMatch]]:
    """Сливает навыки, попавшие в одну тему: сильнейший уровень и общий evidence."""
    merged: dict[uuid.UUID, tuple[ExtractedSkill, TopicMatch]] = {}
    for skill, match in zip(skills, matches, strict=True):
        current = merged.get(match.topic_id)
        if current is None:
            merged[match.topic_id] = (skill, match)
            continue
        previous, previous_match = current
        evidence_parts = [
            value for value in (previous.evidence, skill.evidence) if value
        ]
        evidence = "; ".join(dict.fromkeys(evidence_parts)) or None
        criticality = (
            "must_have"
            if "must_have" in (previous.criticality, skill.criticality)
            else "nice_to_have"
        )
        merged[match.topic_id] = (
            replace(
                previous,
                level=max(previous.level, skill.level),
                weight=max(previous.weight, skill.weight),
                confidence=max(previous.confidence, skill.confidence),
                evidence=evidence,
                criticality=criticality,
            ),
            previous_match,
        )
    return [skill for skill, _ in merged.values()], [
        match for _, match in merged.values()
    ]


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
