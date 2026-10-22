"""Загрузка онтологии из БД для сопоставления навыков."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.embeddings.base import EmbeddingProvider
from app.models import Topic
from app.ontology.topics import ONTOLOGY_TOPICS
from app.services.normalization import (
    DEFAULT_EMBEDDING_THRESHOLD,
    DEFAULT_FUZZY_THRESHOLD,
    SkillMatcher,
    TopicIndex,
    TopicRecord,
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
    """Строит индекс тем онтологии из БД (включая автосозданные темы)."""
    topics = (await session.scalars(select(Topic).order_by(Topic.key))).all()
    records = [
        TopicRecord(
            id=topic.id,
            key=topic.key,
            name=topic.name,
            description=topic.description or "",
            aliases=tuple(topic.aliases or ()),
        )
        for topic in topics
    ]
    return TopicIndex(records)


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
