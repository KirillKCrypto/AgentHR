"""Планы подготовки по темам из резюме."""

import hashlib
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    InterviewSession,
    InterviewTurn,
    LearningPlan,
    PlanItem,
    Resume,
    Topic,
    UserSkillState,
    Vacancy,
    VacancySkill,
)
from app.services.learning_topics import NON_LEARNING_TOPIC_KEYS
from app.services.questions import count_by_topic

MIN_TOPICS = 5
MAX_TOPICS = 12
# Версия алгоритма плана: старые отпечатки не переиспользуются после смены логики.
PLAN_VERSION = "5"
DEFAULT_TARGET_LEVEL = 80


class PlanError(ValueError):
    """План нельзя построить по текущим данным."""


class PlanNotFoundError(LookupError):
    """План не найден у пользователя."""


@dataclass(frozen=True)
class PlanTopic:
    """Тема плана с текущим и целевым уровнем."""

    topic_id: uuid.UUID
    topic_key: str
    topic_name: str
    category: str | None
    current_level: int
    confidence: float
    target_level: int
    criticality: str
    priority: float
    reason: str
    question_count: int = 0


@dataclass(frozen=True)
class PlanSnapshot:
    """План подготовки и его темы."""

    id: uuid.UUID
    user_id: uuid.UUID
    vacancy_id: uuid.UUID | None
    vacancy_title: str | None
    resume_id: uuid.UUID | None
    resume_title: str | None
    title: str
    status: str
    items: tuple[PlanTopic, ...]
    reused: bool = False


@dataclass(frozen=True)
class PlanSummary:
    """Краткая карточка плана для списка."""

    id: uuid.UUID
    title: str
    status: str
    vacancy_id: uuid.UUID | None
    vacancy_title: str | None
    resume_id: uuid.UUID | None
    topic_count: int
    kind: str = "general"
    created_at: datetime | None = None
    is_current: bool = False


@dataclass
class PlanCandidate:
    """Тема-кандидат с накопленным приоритетом слабости."""

    topic: Topic
    current_level: int
    confidence: float
    target_level: int
    criticality: str
    priority: float
    reasons: list[str]

    def add_reason(self, reason: str) -> None:
        """Добавляет причину без повторов."""
        if reason not in self.reasons:
            self.reasons.append(reason)


async def create_plan(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    vacancy_id: uuid.UUID | None = None,
) -> PlanSnapshot:
    """Строит план из слабых и незатронутых тем, а не из сильных навыков."""
    vacancy: Vacancy | None = None
    vacancy_rows: list[tuple[VacancySkill, Topic]] = []
    if vacancy_id is not None:
        vacancy = await session.get(Vacancy, vacancy_id)
        if vacancy is None or vacancy.user_id != user_id:
            raise PlanNotFoundError("Вакансия не найдена")
        vacancy_rows = list(
            (
                await session.execute(
                    select(VacancySkill, Topic)
                    .join(Topic, Topic.id == VacancySkill.topic_id)
                    .where(
                        VacancySkill.vacancy_id == vacancy.id,
                        Topic.status == "canonical",
                        Topic.key.not_in(NON_LEARNING_TOPIC_KEYS),
                    )
                )
            ).all()
        )

    profile_rows = list(
        (
            await session.execute(
                select(UserSkillState, Topic)
                .join(Topic, Topic.id == UserSkillState.topic_id)
                .where(
                    UserSkillState.user_id == user_id,
                    Topic.status == "canonical",
                    Topic.key.not_in(NON_LEARNING_TOPIC_KEYS),
                    UserSkillState.proficiency > 0,
                )
            )
        ).all()
    )
    if not profile_rows and not vacancy_rows:
        raise PlanError("Профиль пуст: сначала загрузите резюме")

    active_resume = await session.scalar(
        select(Resume).where(Resume.user_id == user_id, Resume.is_active.is_(True))
    )
    resume_id = active_resume.id if active_resume is not None else None
    fingerprint = await _plan_fingerprint(session, user_id, vacancy, resume_id)
    latest = await session.scalar(
        _active_plan_query(user_id, vacancy_id, resume_id)
        .order_by(LearningPlan.created_at.desc())
        .limit(1)
    )
    if latest is not None:
        if latest.profile_fingerprint is None and latest.resume_id == resume_id:
            latest.profile_fingerprint = fingerprint
            await session.commit()
            await _archive_other_active_plans(
                session, user_id, latest.vacancy_id, resume_id, latest.id
            )
            return replace(await get_plan(session, user_id, latest.id), reused=True)
        if latest.profile_fingerprint == fingerprint and latest.resume_id == resume_id:
            await _archive_other_active_plans(
                session, user_id, latest.vacancy_id, resume_id, latest.id
            )
            return replace(await get_plan(session, user_id, latest.id), reused=True)

    candidates = await _build_candidates(
        session,
        user_id,
        vacancy,
        vacancy_rows,
        profile_rows,
    )
    selected = _select_candidates(candidates)
    if not selected:
        raise PlanError("Нет тем для плана: сначала загрузите резюме или вакансию")

    await session.execute(
        update(LearningPlan)
        .where(
            LearningPlan.user_id == user_id,
            LearningPlan.status == "active",
            (
                LearningPlan.vacancy_id.is_(None)
                if vacancy is None
                else LearningPlan.vacancy_id == vacancy.id
            ),
            (
                LearningPlan.resume_id.is_(None)
                if resume_id is None
                else LearningPlan.resume_id == resume_id
            ),
        )
        .values(status="archived")
    )

    plan = LearningPlan(
        user_id=user_id,
        vacancy_id=vacancy.id if vacancy is not None else None,
        resume_id=resume_id,
        title=(
            f"Подготовка: {vacancy.title}"
            if vacancy is not None and vacancy.title
            else "План подготовки"
        ),
        status="active",
        profile_fingerprint=fingerprint,
    )
    session.add(plan)
    await session.flush()

    question_counts = await count_by_topic(session, [item.topic.id for item in selected])
    items: list[PlanTopic] = []
    for position, candidate in enumerate(selected, start=1):
        reason = "; ".join(candidate.reasons) or (
            f"низкий уровень в профиле: {candidate.current_level}%"
        )
        session.add(
            PlanItem(
                plan_id=plan.id,
                topic_id=candidate.topic.id,
                position=position,
                current_level=candidate.current_level,
                target_level=candidate.target_level,
                criticality=candidate.criticality,
                confidence=candidate.confidence,
                priority=round(candidate.priority, 3),
                reason=reason,
            )
        )
        items.append(
            PlanTopic(
                topic_id=candidate.topic.id,
                topic_key=candidate.topic.key,
                topic_name=candidate.topic.name,
                category=candidate.topic.category,
                current_level=candidate.current_level,
                confidence=candidate.confidence,
                target_level=candidate.target_level,
                criticality=candidate.criticality,
                priority=round(candidate.priority, 3),
                reason=reason,
                question_count=question_counts.get(candidate.topic.id, 0),
            )
        )
    await session.commit()
    return PlanSnapshot(
        id=plan.id,
        user_id=user_id,
        vacancy_id=plan.vacancy_id,
        vacancy_title=vacancy.title if vacancy is not None else None,
        resume_id=resume_id,
        resume_title=active_resume.title if active_resume is not None else None,
        title=plan.title,
        status=plan.status,
        items=tuple(items),
    )


def _active_plan_query(
    user_id: uuid.UUID,
    vacancy_id: uuid.UUID | None,
    resume_id: uuid.UUID | None,
):
    """Активный план для того же источника, вакансии и резюме."""
    vacancy_filter = (
        LearningPlan.vacancy_id.is_(None)
        if vacancy_id is None
        else LearningPlan.vacancy_id == vacancy_id
    )
    resume_filter = (
        LearningPlan.resume_id.is_(None)
        if resume_id is None
        else LearningPlan.resume_id == resume_id
    )
    return select(LearningPlan).where(
        LearningPlan.user_id == user_id,
        LearningPlan.status == "active",
        vacancy_filter,
        resume_filter,
    )


async def _archive_other_active_plans(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy_id: uuid.UUID | None,
    resume_id: uuid.UUID | None,
    keep_id: uuid.UUID,
) -> None:
    """Оставляет ровно один активный план для вакансии и резюме."""
    vacancy_filter = (
        LearningPlan.vacancy_id.is_(None)
        if vacancy_id is None
        else LearningPlan.vacancy_id == vacancy_id
    )
    resume_filter = (
        LearningPlan.resume_id.is_(None)
        if resume_id is None
        else LearningPlan.resume_id == resume_id
    )
    await session.execute(
        update(LearningPlan)
        .where(
            LearningPlan.user_id == user_id,
            LearningPlan.status == "active",
            LearningPlan.id != keep_id,
            vacancy_filter,
            resume_filter,
        )
        .values(status="archived")
    )
    await session.commit()


async def _build_candidates(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy: Vacancy | None,
    vacancy_rows: list[tuple[VacancySkill, Topic]],
    profile_rows: list[tuple[UserSkillState, Topic]],
) -> list[PlanCandidate]:
    """Собирает темы по слабости: разрывы, интервью и уверенность."""
    states = {state.topic_id: state for state, _ in profile_rows}
    candidates: dict[uuid.UUID, PlanCandidate] = {}

    def candidate_for(
        topic: Topic,
        target: int = DEFAULT_TARGET_LEVEL,
        criticality: str = "nice_to_have",
    ) -> PlanCandidate:
        existing = candidates.get(topic.id)
        if existing is not None:
            existing.target_level = max(existing.target_level, target)
            if criticality == "must_have":
                existing.criticality = "must_have"
            return existing
        state = states.get(topic.id)
        current = state.proficiency if state is not None else 0
        confidence = state.confidence if state is not None else 0.0
        created = PlanCandidate(
            topic=topic,
            current_level=current,
            confidence=confidence,
            target_level=target,
            criticality=criticality,
            priority=0.0,
            reasons=[],
        )
        candidates[topic.id] = created
        return created

    # 1. Разрывы вакансии: главный источник слабых тем.
    vacancy_targets: dict[uuid.UUID, int] = {}
    vacancy_criticality: dict[uuid.UUID, str] = {}
    for skill, topic in vacancy_rows:
        criticality = skill.criticality or "must_have"
        if criticality == "must_have":
            vacancy_criticality[topic.id] = "must_have"
        else:
            vacancy_criticality.setdefault(topic.id, "nice_to_have")
        candidate = candidate_for(
            topic,
            max(skill.required_level, 1),
            criticality,
        )
        target = candidate.target_level
        vacancy_targets[topic.id] = target
        gap = max(0, target - candidate.current_level)
        if gap <= 0:
            if candidate.criticality == "must_have":
                candidate.reasons.append(
                    "обязательное требование: подтвердить уровень тестом"
                )
            continue
        factor = 1.6 if skill.criticality == "must_have" else 0.7
        priority = (gap / max(target, 1)) * 100 * skill.weight * factor
        if candidate.current_level == 0:
            priority += 20
            candidate.add_reason(
                f"тема вакансии не подтверждена в профиле (требуется {target}%)"
            )
        else:
            candidate.add_reason(
                f"разрыв {gap}: требуется {target}%, в профиле {candidate.current_level}%"
            )
        candidate.priority += priority

    # 2. Слабые ответы и незатронутые темы последнего интервью.
    interview = await _latest_interview(session, user_id, vacancy)
    if interview is not None:
        turn_rows = list(
            (
                await session.execute(
                    select(InterviewTurn, Topic)
                    .join(Topic, Topic.id == InterviewTurn.topic_id)
                    .where(InterviewTurn.session_id == interview.id)
                )
            ).all()
        )
        asked = {turn.topic_id for turn, _ in turn_rows}
        for turn, topic in turn_rows:
            if turn.score is None or turn.score >= 70:
                continue
            candidate = candidate_for(
                topic,
                vacancy_targets.get(topic.id, DEFAULT_TARGET_LEVEL),
                vacancy_criticality.get(topic.id, "nice_to_have"),
            )
            candidate.priority += (70 - turn.score) * 1.2 + 10
            candidate.add_reason(f"слабый ответ в интервью: {round(turn.score)}/100")
        if vacancy is not None:
            for skill, topic in vacancy_rows:
                if topic.id in asked:
                    continue
                candidate = candidate_for(
                    topic,
                    vacancy_targets.get(topic.id, DEFAULT_TARGET_LEVEL),
                    vacancy_criticality.get(topic.id, "nice_to_have"),
                )
                factor = 1.4 if skill.criticality == "must_have" else 0.8
                candidate.priority += 60 * skill.weight * factor
                candidate.add_reason("не затронуто в интервью по вакансии")

    # 3. Слабые темы профиля: основа плана без вакансии и добор до минимума.
    for state, topic in profile_rows:
        due = (
            state.review_due_at is not None
            and state.review_due_at <= datetime.now(UTC)
        )
        if due:
            candidate = candidate_for(
                topic,
                vacancy_targets.get(topic.id, DEFAULT_TARGET_LEVEL),
                vacancy_criticality.get(topic.id, "nice_to_have"),
            )
            candidate.priority += 15
            candidate.add_reason("пора повторить тему")
        if topic.id in vacancy_targets:
            continue
        candidate = candidate_for(topic, DEFAULT_TARGET_LEVEL)
        confidence_factor = 1 - 0.35 * candidate.confidence
        weakness = (100 - candidate.current_level) * confidence_factor
        scale = 0.6 if vacancy is not None else 1.0
        candidate.priority += weakness * scale
        candidate.add_reason(f"низкий уровень в профиле: {candidate.current_level}%")
        if candidate.confidence < 0.5:
            candidate.add_reason(
                f"низкая уверенность {round(candidate.confidence * 100)}%"
            )

    return list(candidates.values())


def _select_candidates(candidates: list[PlanCandidate]) -> list[PlanCandidate]:
    """Все обязательные темы плюс самые слабые до общего лимита.

    Лимит MAX_TOPICS не должен скрывать must-have: иначе пользователь не может
    подтвердить навык, который вакансия считает обязательным.
    """
    must_have = [candidate for candidate in candidates if candidate.criticality == "must_have"]
    must_have.sort(key=lambda item: (item.current_level, item.topic.name))
    selected = list(must_have)
    chosen = {item.topic.id for item in selected}

    nice = [
        candidate
        for candidate in candidates
        if candidate.topic.id not in chosen and candidate.priority > 0
    ]
    nice.sort(key=lambda item: (-item.priority, item.current_level, item.topic.name))
    target_total = max(MAX_TOPICS, len(selected))
    selected.extend(nice[: max(0, target_total - len(selected))])

    if len(selected) < MIN_TOPICS:
        chosen = {item.topic.id for item in selected}
        rest = [
            candidate
            for candidate in candidates
            if candidate.topic.id not in chosen and candidate.criticality != "must_have"
        ]
        rest.sort(
            key=lambda item: (item.current_level, item.confidence, item.topic.name)
        )
        selected.extend(rest[: MIN_TOPICS - len(selected)])
    return selected


async def _latest_interview(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy: Vacancy | None,
) -> InterviewSession | None:
    """Последнее завершённое интервью: по вакансии или любое."""
    query = select(InterviewSession).where(
        InterviewSession.user_id == user_id,
        InterviewSession.status == "completed",
    )
    if vacancy is not None:
        query = query.where(InterviewSession.vacancy_id == vacancy.id)
    return await session.scalar(
        query.order_by(InterviewSession.finished_at.desc()).limit(1)
    )


async def get_plan(session: AsyncSession, user_id: uuid.UUID, plan_id: uuid.UUID) -> PlanSnapshot:
    """Возвращает план пользователя с темами."""
    plan = await session.get(LearningPlan, plan_id)
    if plan is None or plan.user_id != user_id or plan.status == "archived":
        raise PlanNotFoundError("План не найден")

    rows = (
        await session.execute(
            select(PlanItem, Topic)
            .join(Topic, Topic.id == PlanItem.topic_id)
            .where(PlanItem.plan_id == plan.id)
            .order_by(PlanItem.position)
        )
    ).all()
    vacancy_title = None
    if plan.vacancy_id is not None:
        vacancy = await session.get(Vacancy, plan.vacancy_id)
        vacancy_title = vacancy.title if vacancy is not None else None
    resume_title = None
    if plan.resume_id is not None:
        resume = await session.get(Resume, plan.resume_id)
        resume_title = resume.title if resume is not None else None

    question_counts = await count_by_topic(session, [topic.id for _, topic in rows])

    return PlanSnapshot(
        id=plan.id,
        user_id=plan.user_id,
        vacancy_id=plan.vacancy_id,
        vacancy_title=vacancy_title,
        resume_id=plan.resume_id,
        resume_title=resume_title,
        title=plan.title,
        status=plan.status,
        items=tuple(
            PlanTopic(
                topic_id=topic.id,
                topic_key=topic.key,
                topic_name=topic.name,
                category=topic.category,
                current_level=item.current_level,
                confidence=item.confidence,
                target_level=item.target_level,
                criticality=item.criticality,
                priority=item.priority,
                reason=item.reason,
                question_count=question_counts.get(topic.id, 0),
            )
            for item, topic in rows
        ),
    )


async def list_plans(session: AsyncSession, user_id: uuid.UUID) -> list[PlanSummary]:
    """Список планов пользователя, новые сверху."""
    active_resume_id = await session.scalar(
        select(Resume.id).where(Resume.user_id == user_id, Resume.is_active.is_(True))
    )
    plans = (
        await session.scalars(
            select(LearningPlan)
            .where(LearningPlan.user_id == user_id)
            .order_by(LearningPlan.created_at.desc())
        )
    ).all()
    vacancy_ids = {plan.vacancy_id for plan in plans if plan.vacancy_id is not None}
    vacancy_titles: dict[uuid.UUID, str | None] = {}
    if vacancy_ids:
        vacancy_titles = {
            vacancy_id: title
            for vacancy_id, title in (
                await session.execute(
                    select(Vacancy.id, Vacancy.title).where(Vacancy.id.in_(vacancy_ids))
                )
            ).all()
        }

    result: list[PlanSummary] = []
    for plan in plans:
        count = (
            await session.scalar(
                select(func.count()).select_from(PlanItem).where(PlanItem.plan_id == plan.id)
            )
        ) or 0
        result.append(
            PlanSummary(
                id=plan.id,
                title=plan.title,
                status=plan.status,
                vacancy_id=plan.vacancy_id,
                vacancy_title=vacancy_titles.get(plan.vacancy_id) if plan.vacancy_id else None,
                resume_id=plan.resume_id,
                topic_count=count,
                kind="vacancy" if plan.vacancy_id is not None else "general",
                created_at=plan.created_at,
                is_current=(
                    plan.status == "active"
                    and active_resume_id is not None
                    and plan.resume_id == active_resume_id
                ),
            )
        )
    return result


async def _plan_fingerprint(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy: Vacancy | None,
    resume_id: uuid.UUID | None,
) -> str:
    """Отпечаток источника плана: профиль, вакансия, резюме и интервью."""
    states = (
        await session.scalars(
            select(UserSkillState)
            .where(UserSkillState.user_id == user_id)
            .order_by(UserSkillState.topic_id)
        )
    ).all()
    parts = [
        f"plan:{PLAN_VERSION}",
        f"resume:{resume_id}" if resume_id is not None else "resume:none",
        *[
            ":".join(
                [
                    str(state.topic_id),
                    str(state.proficiency),
                    str(state.confidence),
                    state.source,
                    state.evidence_type,
                    str(state.verified_level),
                    state.review_due_at.isoformat() if state.review_due_at else "",
                    str(state.review_interval_days),
                ]
            )
            for state in states
        ],
    ]

    if vacancy is None:
        parts.append("vacancy:none")
    else:
        parts.append(f"vacancy:{vacancy.id}")
        requirement_rows = (
            await session.execute(
                select(
                    VacancySkill.topic_id,
                    VacancySkill.required_level,
                    VacancySkill.weight,
                    VacancySkill.criticality,
                )
                .where(VacancySkill.vacancy_id == vacancy.id)
                .order_by(VacancySkill.topic_id)
            )
        ).all()
        parts.extend(
            ":".join(
                [
                    str(topic_id),
                    str(required_level),
                    str(weight),
                    criticality,
                ]
            )
            for topic_id, required_level, weight, criticality in requirement_rows
        )

    interview = await _latest_interview(session, user_id, vacancy)
    parts.append(
        "interview:none"
        if interview is None
        else f"interview:{interview.id}:{interview.finished_at}"
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
