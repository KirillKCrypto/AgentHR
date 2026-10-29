"""Ревью provisional-тем: approve, reject и merge с переносом связей."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OntologyReviewAction,
    ResumeSkill,
    Topic,
    TopicAlias,
    TopicCandidate,
    TopicPrerequisite,
    UserSkillState,
    VacancySkill,
)

MAX_CONFIDENCE = 0.95


class ReviewError(Exception):
    """Некорректная операция ревью онтологии."""


@dataclass(frozen=True)
class ReviewTopicInfo:
    """Сводка provisional-темы для CLI/админки."""

    id: uuid.UUID
    key: str
    name: str
    status: str
    origin: str
    skill_count: int
    candidate_count: int
    created_at: datetime | None


async def list_review_topics(
    session: AsyncSession,
    *,
    status: str = "provisional",
) -> list[ReviewTopicInfo]:
    """Возвращает темы выбранного статуса со счётчиками связей."""
    topics = (
        await session.scalars(
            select(Topic).where(Topic.status == status).order_by(Topic.created_at, Topic.key)
        )
    ).all()
    result: list[ReviewTopicInfo] = []
    for topic in topics:
        skill_count = (
            await session.scalar(
                select(func.count())
                .select_from(ResumeSkill)
                .where(ResumeSkill.topic_id == topic.id)
            )
        ) or 0
        vacancy_count = (
            await session.scalar(
                select(func.count())
                .select_from(VacancySkill)
                .where(VacancySkill.topic_id == topic.id)
            )
        ) or 0
        candidate_count = (
            await session.scalar(
                select(func.count())
                .select_from(TopicCandidate)
                .where(TopicCandidate.topic_id == topic.id)
            )
        ) or 0
        result.append(
            ReviewTopicInfo(
                id=topic.id,
                key=topic.key,
                name=topic.name,
                status=topic.status,
                origin=topic.origin,
                skill_count=skill_count + vacancy_count,
                candidate_count=candidate_count,
                created_at=topic.created_at,
            )
        )
    return result


async def approve_topic(
    session: AsyncSession,
    topic_key: str,
    *,
    actor: str = "cli",
    details: dict | None = None,
) -> Topic:
    """Подтверждает provisional-тему как canonical."""
    topic = await _load_topic(session, topic_key)
    if topic.status != "provisional":
        raise ReviewError(f"Тема {topic.key!r} имеет статус {topic.status!r}, нужен provisional")

    topic.status = "canonical"
    await session.execute(
        update(TopicCandidate).where(TopicCandidate.topic_id == topic.id).values(status="approved")
    )
    record_review_action(session, "approve", topic, actor=actor, details=details)
    await session.flush()
    return topic


async def reject_topic(
    session: AsyncSession,
    topic_key: str,
    *,
    actor: str = "cli",
    details: dict | None = None,
) -> Topic:
    """Отклоняет provisional-тему, если на неё нет ссылок из документов."""
    topic = await _load_topic(session, topic_key)
    if topic.status != "provisional":
        raise ReviewError(f"Тема {topic.key!r} имеет статус {topic.status!r}, нужен provisional")

    skill_count = await _skill_ref_count(session, topic.id)
    if skill_count:
        raise ReviewError(
            f"Тему {topic.key!r} нельзя отклонить: на неё ссылаются {skill_count} навыков. "
            "Сначала выполните merge в подходящую тему."
        )

    topic.status = "rejected"
    await session.execute(
        update(TopicCandidate).where(TopicCandidate.topic_id == topic.id).values(status="rejected")
    )
    await session.execute(
        update(TopicAlias).where(TopicAlias.topic_id == topic.id).values(status="rejected")
    )
    record_review_action(session, "reject", topic, actor=actor, details=details)
    await session.flush()
    return topic


async def merge_topics(
    session: AsyncSession,
    source_key: str,
    target_key: str,
    *,
    actor: str = "cli",
    details: dict | None = None,
) -> tuple[Topic, Topic]:
    """Переносит все связи и алиасы source в target, помечая source merged."""
    source = await _load_topic(session, source_key)
    target = await _load_topic(session, target_key)
    if source.id == target.id:
        raise ReviewError("Нельзя объединить тему с самой собой")
    if source.status != "provisional":
        raise ReviewError(f"Источник {source.key!r} должен быть provisional")
    if target.status not in ("canonical", "provisional"):
        raise ReviewError(
            f"Цель {target.key!r} не может принимать merge из статуса {target.status}"
        )

    skills_moved = await _skill_ref_count(session, source.id)
    await session.execute(
        update(ResumeSkill).where(ResumeSkill.topic_id == source.id).values(topic_id=target.id)
    )
    await session.execute(
        update(VacancySkill).where(VacancySkill.topic_id == source.id).values(topic_id=target.id)
    )
    await _merge_user_states(session, source.id, target.id)
    await _transfer_edges(session, source.id, target.id)
    await _transfer_aliases(session, source.id, target.id)
    await session.execute(
        update(TopicCandidate)
        .where(TopicCandidate.topic_id == source.id)
        .values(topic_id=target.id, status="merged")
    )

    source.status = "merged"
    source.canonical_topic_id = target.id
    audit_details = {
        "source_key": source.key,
        "target_key": target.key,
        "skills_moved": skills_moved,
    }
    if details:
        audit_details.update(details)
    record_review_action(
        session,
        "merge",
        source,
        target=target,
        actor=actor,
        details=audit_details,
    )
    await session.flush()
    return source, target


async def _load_topic(session: AsyncSession, key: str) -> Topic:
    """Загружает тему по ключу или поднимает понятную ошибку."""
    topic = await session.scalar(select(Topic).where(Topic.key == key))
    if topic is None:
        raise ReviewError(f"Тема {key!r} не найдена")
    return topic


async def _skill_ref_count(session: AsyncSession, topic_id: uuid.UUID) -> int:
    """Сколько навыков документов ссылается на тему."""
    resume_count = (
        await session.scalar(
            select(func.count()).select_from(ResumeSkill).where(ResumeSkill.topic_id == topic_id)
        )
    ) or 0
    vacancy_count = (
        await session.scalar(
            select(func.count()).select_from(VacancySkill).where(VacancySkill.topic_id == topic_id)
        )
    ) or 0
    return resume_count + vacancy_count


async def _merge_user_states(
    session: AsyncSession,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
) -> None:
    """Переносит состояния профиля, объединяя оценки при конфликте."""
    source_states = (
        await session.scalars(select(UserSkillState).where(UserSkillState.topic_id == source_id))
    ).all()
    for state in source_states:
        target_state = await session.scalar(
            select(UserSkillState).where(
                UserSkillState.user_id == state.user_id,
                UserSkillState.topic_id == target_id,
            )
        )
        if target_state is None:
            state.topic_id = target_id
            continue

        total_confidence = target_state.confidence + state.confidence
        if total_confidence > 0:
            target_state.proficiency = round(
                (
                    target_state.proficiency * target_state.confidence
                    + state.proficiency * state.confidence
                )
                / total_confidence
            )
        target_state.confidence = min(
            MAX_CONFIDENCE, max(target_state.confidence, state.confidence)
        )
        target_state.evidence = list(target_state.evidence or []) + list(state.evidence or [])
        assessed = [value for value in (target_state.last_assessed, state.last_assessed) if value]
        target_state.last_assessed = max(assessed) if assessed else None
        await session.delete(state)


async def _transfer_edges(
    session: AsyncSession,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
) -> None:
    """Перенаправляет рёбра REQUIRES с source на target без дублей и self-edge."""
    outgoing = (
        await session.scalars(
            select(TopicPrerequisite).where(TopicPrerequisite.topic_id == source_id)
        )
    ).all()
    for edge in outgoing:
        if edge.prerequisite_id == target_id:
            await session.delete(edge)
            continue
        existing = await session.scalar(
            select(TopicPrerequisite).where(
                TopicPrerequisite.topic_id == target_id,
                TopicPrerequisite.prerequisite_id == edge.prerequisite_id,
            )
        )
        if existing is not None:
            await session.delete(edge)
        else:
            edge.topic_id = target_id

    incoming = (
        await session.scalars(
            select(TopicPrerequisite).where(TopicPrerequisite.prerequisite_id == source_id)
        )
    ).all()
    for edge in incoming:
        if edge.topic_id == target_id:
            await session.delete(edge)
            continue
        existing = await session.scalar(
            select(TopicPrerequisite).where(
                TopicPrerequisite.topic_id == edge.topic_id,
                TopicPrerequisite.prerequisite_id == target_id,
            )
        )
        if existing is not None:
            await session.delete(edge)
        else:
            edge.prerequisite_id = target_id


async def _transfer_aliases(
    session: AsyncSession,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
) -> None:
    """Переносит алиасы; конфликтующие нормализованные формы удаляет."""
    aliases = (
        await session.scalars(select(TopicAlias).where(TopicAlias.topic_id == source_id))
    ).all()
    for alias in aliases:
        existing = await session.scalar(
            select(TopicAlias).where(TopicAlias.normalized_alias == alias.normalized_alias)
        )
        if existing is not None and existing.id != alias.id:
            await session.delete(alias)
        else:
            alias.topic_id = target_id


def record_review_action(
    session: AsyncSession,
    action: str,
    source: Topic,
    *,
    target: Topic | None = None,
    actor: str,
    details: dict | None = None,
) -> None:
    """Добавляет запись в аудит ревью онтологии (ручное или автоматическое)."""
    session.add(
        OntologyReviewAction(
            action=action,
            source_topic_id=source.id,
            target_topic_id=target.id if target is not None else None,
            actor=actor,
            details=details or {},
        )
    )
