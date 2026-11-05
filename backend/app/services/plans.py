"""Планы подготовки по темам из резюме."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearningPlan, PlanItem, Topic, UserSkillState, Vacancy, VacancySkill

MIN_TOPICS = 5
MAX_TOPICS = 12


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
    priority: float
    reason: str


@dataclass(frozen=True)
class PlanSnapshot:
    """План подготовки и его темы."""

    id: uuid.UUID
    user_id: uuid.UUID
    vacancy_id: uuid.UUID | None
    vacancy_title: str | None
    title: str
    status: str
    items: tuple[PlanTopic, ...]


@dataclass(frozen=True)
class PlanSummary:
    """Краткая карточка плана для списка."""

    id: uuid.UUID
    title: str
    status: str
    vacancy_id: uuid.UUID | None
    topic_count: int


async def create_plan(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    vacancy_id: uuid.UUID | None = None,
) -> PlanSnapshot:
    """Строит план из самых сильных тем резюме пользователя."""
    vacancy = None
    required_by_topic: dict[uuid.UUID, int] = {}
    if vacancy_id is not None:
        vacancy = await session.get(Vacancy, vacancy_id)
        if vacancy is None or vacancy.user_id != user_id:
            raise PlanNotFoundError("Вакансия не найдена")
        rows = (
            await session.execute(
                select(VacancySkill.topic_id, VacancySkill.required_level).where(
                    VacancySkill.vacancy_id == vacancy.id
                )
            )
        ).all()
        for topic_id, required_level in rows:
            if topic_id is not None:
                required_by_topic[topic_id] = max(
                    required_by_topic.get(topic_id, 0), required_level
                )

    rows = (
        await session.execute(
            select(UserSkillState, Topic)
            .join(Topic, Topic.id == UserSkillState.topic_id)
            .where(
                UserSkillState.user_id == user_id,
                Topic.status == "canonical",
                UserSkillState.proficiency > 0,
            )
        )
    ).all()
    if not rows:
        raise PlanError("Профиль пуст: сначала загрузите резюме")

    candidates: list[tuple[float, UserSkillState, Topic]] = []
    for state, topic in rows:
        score = state.proficiency * (0.6 + 0.4 * state.confidence)
        candidates.append((round(score, 3), state, topic))

    candidates.sort(key=lambda pair: (pair[0], pair[1].proficiency, pair[2].name), reverse=True)
    selected = candidates[:MAX_TOPICS]

    plan = LearningPlan(
        user_id=user_id,
        vacancy_id=vacancy.id if vacancy is not None else None,
        title=(
            f"Подготовка: {vacancy.title}"
            if vacancy is not None and vacancy.title
            else "План подготовки"
        ),
        status="active",
    )
    session.add(plan)
    await session.flush()

    items: list[PlanTopic] = []
    for position, (score, state, topic) in enumerate(selected, start=1):
        target = required_by_topic.get(topic.id, 100)
        reason_parts = [
            f"Ключевой навык резюме: {state.proficiency}%",
            f"уверенность {round(state.confidence * 100)}%",
        ]
        if topic.id in required_by_topic:
            reason_parts.append(f"в вакансии требуется {target}%")
        session.add(
            PlanItem(
                plan_id=plan.id,
                topic_id=topic.id,
                position=position,
                current_level=state.proficiency,
                target_level=target,
                confidence=state.confidence,
                priority=score,
                reason="; ".join(reason_parts),
            )
        )
        items.append(
            PlanTopic(
                topic_id=topic.id,
                topic_key=topic.key,
                topic_name=topic.name,
                category=topic.category,
                current_level=state.proficiency,
                confidence=state.confidence,
                target_level=target,
                priority=score,
                reason="; ".join(reason_parts),
            )
        )
    await session.commit()
    return PlanSnapshot(
        id=plan.id,
        user_id=user_id,
        vacancy_id=plan.vacancy_id,
        vacancy_title=vacancy.title if vacancy is not None else None,
        title=plan.title,
        status=plan.status,
        items=tuple(items),
    )


async def get_plan(session: AsyncSession, user_id: uuid.UUID, plan_id: uuid.UUID) -> PlanSnapshot:
    """Возвращает план пользователя с темами."""
    plan = await session.get(LearningPlan, plan_id)
    if plan is None or plan.user_id != user_id:
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

    return PlanSnapshot(
        id=plan.id,
        user_id=plan.user_id,
        vacancy_id=plan.vacancy_id,
        vacancy_title=vacancy_title,
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
                priority=item.priority,
                reason=item.reason,
            )
            for item, topic in rows
        ),
    )


async def list_plans(session: AsyncSession, user_id: uuid.UUID) -> list[PlanSummary]:
    """Список планов пользователя, новые сверху."""
    plans = (
        await session.scalars(
            select(LearningPlan)
            .where(LearningPlan.user_id == user_id)
            .order_by(LearningPlan.created_at.desc())
        )
    ).all()
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
                topic_count=count,
            )
        )
    return result
