"""Загрузка онтологии из БД и расширение её новыми навыками."""

import hashlib
import re
import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.embeddings.base import EmbeddingProvider
from app.models import ResumeSkill, Topic, TopicAlias, TopicCandidate, VacancySkill
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


async def load_topic_index(
    session: AsyncSession,
    *,
    statuses: Sequence[str] = ("canonical", "provisional"),
    exclude_ids: Sequence[uuid.UUID] = (),
) -> TopicIndex:
    """Строит индекс тем выбранных статусов (по умолчанию canonical и provisional).

    `exclude_ids` исключает проверяемые темы: иначе авто-ревью нашло бы тему
    по её собственному алиасу и попыталось слить её саму с собой.
    """
    excluded = set(exclude_ids)
    topics = [
        topic
        for topic in (
            await session.scalars(
                select(Topic).where(Topic.status.in_(tuple(statuses))).order_by(Topic.key)
            )
        ).all()
        if topic.id not in excluded
    ]
    # Canonical-темы идут первыми, внутри canonical — темы из пакета (origin
    # seed). Индекс использует setdefault, поэтому при одинаковом названии
    # (например, подтверждённая вручную тема и тема из пакета) точное
    # совпадение должно вести в тему пакета, а не в дубликат.
    topics = sorted(
        topics,
        key=lambda topic: (topic.status != "canonical", topic.origin != "seed", topic.key),
    )
    topic_ids = {topic.id for topic in topics}
    alias_rows = (
        await session.scalars(select(TopicAlias).where(TopicAlias.status == "active"))
    ).all()
    aliases_by_topic: dict[uuid.UUID, list[str]] = {}
    for alias in alias_rows:
        # Алиасы тем вне выбранных статусов не попадают в индекс: иначе
        # canonical-индекс «узнавал» бы provisional-тему по её собственному alias.
        if alias.topic_id in topic_ids:
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
            await _record_repeated_mention(
                session,
                topic,
                name,
                evidence,
                source_type=source_type,
                source_id=source_id,
            )
            return topic, False

    candidate = await session.scalar(
        select(TopicCandidate).where(TopicCandidate.normalized_name == normalized)
    )
    if candidate is not None and candidate.topic_id is not None:
        topic = await session.get(Topic, candidate.topic_id)
        if topic is not None and topic.status not in ("merged", "rejected"):
            await _record_repeated_mention(
                session,
                topic,
                name,
                evidence,
                source_type=source_type,
                source_id=source_id,
            )
            return topic, False

    topic_key = _auto_topic_key(normalized)
    existing_topic = await session.scalar(select(Topic).where(Topic.key == topic_key))
    if existing_topic is not None and existing_topic.status not in ("merged", "rejected"):
        await _record_repeated_mention(
            session,
            existing_topic,
            name,
            evidence,
            source_type=source_type,
            source_id=source_id,
        )
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


async def _record_repeated_mention(
    session: AsyncSession,
    topic: Topic,
    name: str,
    evidence: str | None,
    *,
    source_type: str,
    source_id: uuid.UUID,
) -> None:
    """Копит упоминания навыка в уже существующей provisional-теме.

    Без этого повторное упоминание не увеличивает `occurrences` и число
    источников: авто-ревью считало бы, что новых данных нет, и не перепроверяло
    тему. Подтверждённые темы не трогаем — у них нет очереди ревью.
    """
    if topic.status != "provisional":
        return
    await _record_alias_and_candidate(
        session,
        topic,
        name,
        evidence,
        source_type=source_type,
        source_id=source_id,
    )


async def detach_candidate_topic(
    session: AsyncSession,
    source_topic: Topic,
    candidate: TopicCandidate,
) -> Topic:
    """Выносит кандидата из служебной темы переполнения в отдельную тему.

    Навыки документа и алиас переносятся в новую provisional-тему, чтобы её
    можно было проверить обычными правилами ревью: подтвердить или слить.
    """
    normalized = candidate.normalized_name
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(normalized))))

    topic = await _find_reusable_topic(session, normalized)
    if topic is None:
        topic = Topic(
            key=await _free_topic_key(session, _auto_topic_key(normalized)),
            name=_clip(candidate.name, 120) or normalized,
            description=(
                candidate.suggested_description
                or (
                    f"Автоматически созданная тема для навыка «{_clip(candidate.name, 200)}». "
                    "Требует проверки и подтверждения."
                )
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

    await session.execute(
        update(TopicAlias)
        .where(TopicAlias.normalized_alias == normalized)
        .values(topic_id=topic.id)
    )
    candidate.topic_id = topic.id

    for model in (ResumeSkill, VacancySkill):
        skills = (
            await session.scalars(select(model).where(model.topic_id == source_topic.id))
        ).all()
        for skill in skills:
            if _clip(normalize_name(skill.raw_name), 200) == normalized:
                skill.topic_id = topic.id

    await session.flush()
    return topic


async def _find_reusable_topic(session: AsyncSession, normalized: str) -> Topic | None:
    """Ищет provisional-тему, созданную ранее для этого же нормализованного имени."""
    topic = await session.scalar(select(Topic).where(Topic.key == _auto_topic_key(normalized)))
    if topic is None or topic.category == "auto_review":
        return None
    if topic.status != "provisional":
        return None
    return topic


async def _free_topic_key(session: AsyncSession, base: str) -> str:
    """Подбирает свободный ключ темы, если детерминированный уже занят."""
    key = base
    counter = 1
    while await session.scalar(select(Topic.id).where(Topic.key == key)) is not None:
        counter += 1
        key = f"{base[:57]}-{counter}"
    return key


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
