"""Загрузка онтологии из БД и расширение её новыми навыками."""

import hashlib
import re
import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.embeddings.base import EmbeddingProvider
from app.models import Topic, TopicAlias, TopicCandidate
from app.ontology.topics import ONTOLOGY_TOPICS, ONTOLOGY_VERSION
from app.services.normalization import (
    DEFAULT_EMBEDDING_THRESHOLD,
    DEFAULT_FUZZY_THRESHOLD,
    SkillMatcher,
    TopicIndex,
    TopicMatch,
    TopicRecord,
    normalize_name,
)

# Пространство имён для детерминированных id тем пакета онтологии
TOPIC_NAMESPACE = uuid.UUID("6f1d9b2e-3c47-5a8f-9d21-7b6e4f0c8a13")


def load_packaged_topic_index() -> TopicIndex:
    """Индекс тем из пакета онтологии (без БД) — для тестов и офлайн-режима.

    Идентификаторы тем детерминированы (uuid5 от ключа), поэтому индекс
    одинаков на любой машине.
    """
    records = [
        TopicRecord(
            id=uuid.uuid5(TOPIC_NAMESPACE, topic.key),
            key=topic.key,
            name=topic.name,
            description=topic.description,
            aliases=topic.aliases,
        )
        for topic in ONTOLOGY_TOPICS
    ]
    return TopicIndex(records)


async def load_topic_index(session: AsyncSession) -> TopicIndex:
    """Строит индекс canonical- и provisional-тем из БД."""
    topics = (
        await session.scalars(
            select(Topic).where(Topic.status.in_(("canonical", "provisional"))).order_by(Topic.key)
        )
    ).all()
    alias_rows = (
        await session.scalars(select(TopicAlias).where(TopicAlias.status == "active"))
    ).all()
    aliases_by_topic: dict[uuid.UUID, list[str]] = {}
    for alias in alias_rows:
        aliases_by_topic.setdefault(alias.topic_id, []).append(alias.alias)

    records = []
    for topic in topics:
        # Таблица алиасов — источник истины. JSONB используем только если
        # таблица ещё пуста (например, миграция применена, а сид — нет).
        aliases = aliases_by_topic.get(topic.id)
        if aliases is None:
            aliases = list(topic.aliases or ()) if not alias_rows else []
        records.append(
            TopicRecord(
                id=topic.id,
                key=topic.key,
                name=topic.name,
                description=topic.description or "",
                aliases=tuple(aliases),
            )
        )
    return TopicIndex(records)


async def resolve_or_create_topics(
    session: AsyncSession,
    mentions: Sequence[tuple[str, str | None]],
    matches: Sequence[TopicMatch],
    *,
    source_type: str,
    source_id: uuid.UUID,
    auto_topic_limit: int | None = None,
) -> list[TopicMatch]:
    """Гарантирует, что у каждого навыка есть тема.

    Совпавшие навыки возвращаются как есть. Для остальных создаётся
    provisional-тема, алиас и запись в очереди ревью — в текущей транзакции.
    Если лимит новых тем исчерпан, остаток уходит в одну review-тему.
    """
    if len(mentions) != len(matches):
        raise ValueError("Количество навыков и результатов сопоставления не совпадает")

    limit = get_settings().auto_topic_limit if auto_topic_limit is None else auto_topic_limit
    created_count = 0
    resolved: list[TopicMatch] = []
    for (name, evidence), match in zip(mentions, matches, strict=True):
        if match.matched:
            resolved.append(match)
            continue

        allow_create = created_count < max(0, limit)
        result = await _resolve_or_create_topic(
            session,
            name,
            evidence,
            source_type=source_type,
            source_id=source_id,
            allow_create=allow_create,
        )
        if result is None:
            topic = await _get_or_create_review_topic(
                session,
                source_type=source_type,
                source_id=source_id,
            )
            await _record_alias_and_candidate(
                session,
                topic,
                name,
                evidence,
                source_type=source_type,
                source_id=source_id,
            )
        else:
            topic, created = result
            if created:
                created_count += 1

        resolved.append(TopicMatch(topic.id, "provisional", 0.0, topic.key))
    return resolved


async def _resolve_or_create_topic(
    session: AsyncSession,
    name: str,
    evidence: str | None,
    *,
    source_type: str,
    source_id: uuid.UUID,
    allow_create: bool,
) -> tuple[Topic, bool] | None:
    """Возвращает существующую provisional-тему или создаёт новую."""
    normalized = _clip(normalize_name(name), 200)
    if not normalized:
        raise ValueError("Нельзя создать тему для пустого названия навыка")

    # Сериализует одновременное создание одной и той же темы из двух сессий.
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(normalized))))

    alias = await session.scalar(
        select(TopicAlias).where(
            TopicAlias.normalized_alias == normalized,
            TopicAlias.status == "active",
        )
    )
    if alias is not None:
        topic = await session.get(Topic, alias.topic_id)
        if topic is not None and topic.status not in ("merged", "rejected"):
            return topic, False

    candidate = await session.scalar(
        select(TopicCandidate).where(TopicCandidate.normalized_name == normalized)
    )
    if candidate is not None and candidate.topic_id is not None:
        topic = await session.get(Topic, candidate.topic_id)
        if topic is not None and topic.status not in ("merged", "rejected"):
            return topic, False

    topic_key = _auto_topic_key(normalized)
    existing_topic = await session.scalar(select(Topic).where(Topic.key == topic_key))
    if existing_topic is not None and existing_topic.status not in ("merged", "rejected"):
        return existing_topic, False

    if not allow_create:
        return None

    display_name = _clip(name, 120) or normalized
    topic = Topic(
        key=topic_key,
        name=display_name,
        description=(
            f"Автоматически созданная тема для навыка «{_clip(name, 200)}». "
            "Требует проверки и подтверждения."
        ),
        category="auto",
        aliases=[],
        ontology_version=ONTOLOGY_VERSION,
        is_auto_generated=True,
        status="provisional",
        origin="auto",
    )
    session.add(topic)
    await session.flush()
    await _record_alias_and_candidate(
        session,
        topic,
        name,
        evidence,
        source_type=source_type,
        source_id=source_id,
    )
    return topic, True


async def _get_or_create_review_topic(
    session: AsyncSession,
    *,
    source_type: str,
    source_id: uuid.UUID,
) -> Topic:
    """Одна provisional-тема для переполнения лимита в документе."""
    topic_key = f"auto-review-{source_type}-{source_id.hex}"[:64]
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(topic_key))))
    topic = await session.scalar(select(Topic).where(Topic.key == topic_key))
    if topic is not None:
        return topic

    topic = Topic(
        key=topic_key,
        name="Новые навыки (на ревью)",
        description=(
            "Навыки, для которых исчерпан лимит отдельных provisional-тем. Требуют ручного разбора."
        ),
        category="auto_review",
        aliases=[],
        ontology_version=ONTOLOGY_VERSION,
        is_auto_generated=True,
        status="provisional",
        origin="auto",
    )
    session.add(topic)
    await session.flush()
    return topic


async def _record_alias_and_candidate(
    session: AsyncSession,
    topic: Topic,
    name: str,
    evidence: str | None,
    *,
    source_type: str,
    source_id: uuid.UUID,
) -> None:
    """Сохраняет алиас и кандидата для навыка, привязанного к теме."""
    normalized = _clip(normalize_name(name), 200)
    if not normalized:
        raise ValueError("Нельзя сохранить пустой алиас навыка")

    alias_stmt = pg_insert(TopicAlias).values(
        topic_id=topic.id,
        alias=_clip(name, 200) or normalized,
        normalized_alias=normalized,
        source="auto",
        status="active",
    )
    alias_stmt = alias_stmt.on_conflict_do_update(
        index_elements=[TopicAlias.normalized_alias],
        set_={
            "topic_id": alias_stmt.excluded.topic_id,
            "alias": alias_stmt.excluded.alias,
            "source": "auto",
            "status": "active",
        },
    )
    await session.execute(alias_stmt)

    candidate_stmt = pg_insert(TopicCandidate).values(
        name=_clip(name, 200) or normalized,
        normalized_name=normalized,
        suggested_description=topic.description,
        occurrences=1,
        sources=[
            {
                "type": source_type,
                "id": str(source_id),
                "evidence": evidence,
            }
        ],
        status="auto_created",
        topic_id=topic.id,
        ontology_version=ONTOLOGY_VERSION,
    )
    candidate_stmt = candidate_stmt.on_conflict_do_update(
        index_elements=[TopicCandidate.normalized_name],
        set_={
            "occurrences": TopicCandidate.occurrences + 1,
            "sources": TopicCandidate.sources.op("||")(candidate_stmt.excluded.sources),
            "topic_id": candidate_stmt.excluded.topic_id,
            "status": "auto_created",
            "suggested_description": candidate_stmt.excluded.suggested_description,
        },
    )
    await session.execute(candidate_stmt)


def _clip(value: str, limit: int) -> str:
    """Обрезает строку до лимита поля БД."""
    return (value or "").strip()[:limit]


def _auto_topic_key(normalized: str) -> str:
    """Детерминированный ключ provisional-темы с коротким хешем."""
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")[:36] or "skill"
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    return f"auto-{slug}-{digest}"[:64]


def create_skill_matcher(
    index: TopicIndex,
    embedder: EmbeddingProvider | None = None,
    settings: Settings | None = None,
) -> SkillMatcher:
    """Собирает сопоставитель навыков с порогами из настроек."""
    current = settings or get_settings()
    return SkillMatcher(
        index,
        embedder,
        fuzzy_threshold=DEFAULT_FUZZY_THRESHOLD,
        embedding_threshold=current.embedding_threshold or DEFAULT_EMBEDDING_THRESHOLD,
    )
