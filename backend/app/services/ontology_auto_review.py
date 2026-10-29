"""Автоматическое ревью provisional-тем онтологии.

Политика гибридная (решение команды, см. decision log в `AGENTS.md`):

1. Детерминированные правила: точное совпадение с canonical-темой или её
   алиасом и очень высокая семантическая близость → `merge`.
2. Накопленные упоминания в нескольких документах и отсутствие близкой
   canonical-темы → `approve`.
3. Спорные темы уходят в LLM: `approve`, `merge` или `keep`. Решение
   применяется только при уверенности не ниже настроенного порога.
4. Всё остальное остаётся provisional с `auto_review_decision="keep"` и
   пометкой для ручной проверки.

Каждое решение пишется в `ontology_review_actions` с `actor="auto"`, поэтому
автоматизация не скрывает историю изменений онтологии.
"""

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.embeddings.base import EmbeddingProvider, cosine_similarity
from app.llm.base import ChatMessage, LLMError, LLMProvider
from app.models import ResumeSkill, Topic, TopicAlias, TopicCandidate, VacancySkill
from app.services.normalization import TopicIndex, TopicRecord, normalize_name
from app.services.ontology_review import (
    ReviewError,
    approve_topic,
    merge_topics,
    record_review_action,
)
from app.services.topics import load_topic_index

logger = logging.getLogger(__name__)

AUTO_ACTOR = "auto"
REVIEW_SCHEMA_NAME = "ontology_review"
# Сколько ближайших canonical-тем показывать LLM и разрешать как цель merge.
TOP_CANDIDATES = 5
# Запас между «похоже на существующую тему» и «это новая тема»: если лучшая
# canonical-тема слишком близка, авто-approve не применяется.
APPROVE_SIMILARITY_MARGIN = 0.2
MAX_ALIASES = 8

AutoReviewAction = Literal["approve", "merge", "keep"]


@dataclass(frozen=True)
class AutoReviewDecision:
    """Решение автоматического ревью одной темы."""

    topic_key: str
    action: AutoReviewAction
    confidence: float
    reason: str
    source: str
    target_key: str | None = None
    name: str | None = None
    description: str | None = None
    category: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class _SimilarTopic:
    """Canonical-тема и её близость к проверяемой теме."""

    record: TopicRecord
    score: float


@dataclass(frozen=True)
class _TopicFacts:
    """Данные provisional-темы, нужные правилам и LLM."""

    topic: Topic
    names: tuple[str, ...]
    document_count: int
    occurrences: int
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class _LlmReview:
    """Разобранный ответ LLM до применения решения."""

    action: AutoReviewAction
    confidence: float
    reason: str
    target_key: str | None = None
    name: str | None = None
    description: str | None = None
    category: str | None = None
    aliases: tuple[str, ...] = ()


REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "confidence", "reason"],
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["approve", "merge", "keep"],
            "description": "Что сделать с проверяемой темой",
        },
        "target_key": {
            "type": ["string", "null"],
            "description": "Ключ canonical-темы для merge (только из списка кандидатов)",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Уверенность решения",
        },
        "reason": {"type": "string", "description": "Короткое обоснование"},
        "name": {
            "type": ["string", "null"],
            "description": "Уточнённое название темы при approve",
        },
        "description": {
            "type": ["string", "null"],
            "description": "Описание темы при approve",
        },
        "category": {
            "type": ["string", "null"],
            "description": "Категория темы при approve (например, database, frontend)",
        },
        "aliases": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Синонимы темы при approve",
        },
    },
}

REVIEW_SYSTEM_PROMPT = (
    "Ты — куратор онтологии технических навыков для подготовки к собеседованиям.\n"
    "Тебе показывают новую тему, автоматически созданную из навыков вакансий и резюме, "
    "и ближайшие существующие темы онтологии.\n"
    "Выбери одно решение:\n"
    "- approve — это самостоятельный реальный навык, которому нужна собственная тема;\n"
    "- merge — это синоним, вариант написания или подвид одной из перечисленных тем "
    "(target_key обязателен и должен быть из списка);\n"
    "- keep — данных мало, навык выглядит как опечатка/мусор или ты не уверен.\n"
    "Правила:\n"
    "- Не выдумывай target_key, которого нет в списке.\n"
    "- Не дроби онтологию: близкие синонимы лучше merge, чем approve.\n"
    "- В aliases перечисли только реальные синонимы названия, без общих слов.\n"
    "- Если сомневаешься — keep и снижай confidence."
)


async def auto_review_topics(
    session: AsyncSession,
    topic_ids: Sequence[uuid.UUID | None],
    *,
    provider: LLMProvider | None = None,
    embedder: EmbeddingProvider | None = None,
    settings: Settings | None = None,
) -> list[AutoReviewDecision]:
    """Проверяет указанные provisional-темы и применяет безопасные решения."""
    current = settings or get_settings()
    if not current.ontology_auto_review_enabled:
        return []

    ids = [topic_id for topic_id in dict.fromkeys(topic_ids) if topic_id is not None]
    if not ids:
        return []

    topics = (
        await session.scalars(
            select(Topic).where(Topic.id.in_(ids), Topic.status == "provisional")
        )
    ).all()
    if not topics:
        return []

    index = await load_topic_index(session, statuses=("canonical",))

    facts_list: list[_TopicFacts] = []
    for topic in topics:
        facts = await _load_facts(session, topic)
        if _needs_review(topic, facts.occurrences):
            facts_list.append(facts)

    # Сначала темы с большим числом упоминаний: они чаще всего важнее.
    facts_list.sort(key=lambda item: item.occurrences, reverse=True)
    facts_list = facts_list[: max(0, current.ontology_auto_review_max_topics)]
    if not facts_list:
        return []

    # Закрываем читающую транзакцию: LLM-вызовы не должны держать соединение
    # с БД открытым на всё время ревью.
    await session.commit()

    decisions: list[AutoReviewDecision] = []
    for facts in facts_list:
        similar = await _rank_similar(facts, index, embedder)
        try:
            decision = await _decide(
                facts,
                index=index,
                similar=similar,
                provider=provider,
                settings=current,
            )
            # Savepoint: ошибка одной темы не откатывает решения по остальным.
            async with session.begin_nested():
                await _apply(session, facts, decision)
            # Решения независимы: фиксируем каждое, чтобы следующее не ждало
            # конца прогона и не держало транзакцию во время LLM-вызова.
            await session.commit()
            decisions.append(decision)
        except (ReviewError, ValueError) as exc:
            await session.rollback()
            logger.warning(
                "Авто-ревью темы %s пропущено: %s",
                facts.topic.key,
                exc,
            )
        except Exception:
            await session.rollback()
            logger.exception("Авто-ревью темы %s завершилось ошибкой", facts.topic.key)

    return decisions


async def run_auto_review(
    session: AsyncSession,
    topic_ids: Sequence[uuid.UUID | None],
    *,
    provider: LLMProvider | None = None,
    embedder: EmbeddingProvider | None = None,
    settings: Settings | None = None,
) -> list[AutoReviewDecision]:
    """Best-effort обёртка: ошибка ревью не должна ломать загрузку документа."""
    try:
        decisions = await auto_review_topics(
            session,
            topic_ids,
            provider=provider,
            embedder=embedder,
            settings=settings,
        )
        if decisions:
            await session.commit()
        return decisions
    except Exception:
        logger.exception("Автоматическое ревью онтологии не выполнено")
        await session.rollback()
        return []


async def _decide(
    facts: _TopicFacts,
    *,
    index: TopicIndex,
    similar: Sequence[_SimilarTopic],
    provider: LLMProvider | None,
    settings: Settings,
) -> AutoReviewDecision:
    """Определяет решение: сначала правила, затем LLM, иначе keep."""
    topic = facts.topic

    # Служебная тема переполнения объединяет разнородные навыки. Подтверждать
    # или сливать её целиком нельзя — только ручной разбор.
    if topic.category == "auto_review":
        return AutoReviewDecision(
            topic_key=topic.key,
            action="keep",
            confidence=0.0,
            reason="Служебная review-тема переполнения требует ручного разбора",
            source="rule",
        )

    # 1. Точное совпадение с canonical-темой или её алиасом.
    for name in facts.names:
        record = index.find_exact(name) or index.find_alias(name)
        if record is not None:
            return AutoReviewDecision(
                topic_key=topic.key,
                action="merge",
                confidence=1.0,
                reason=f"Совпадение с canonical-темой {record.key!r}",
                source="rule",
                target_key=record.key,
            )

    best = similar[0] if similar else None

    # 2. Очень высокая семантическая близость — безопаснее слить.
    if best is not None and best.score >= settings.ontology_auto_merge_similarity:
        return AutoReviewDecision(
            topic_key=topic.key,
            action="merge",
            confidence=round(best.score, 3),
            reason=(
                f"Семантическая близость {best.score:.2f} к теме {best.record.key!r} "
                "выше порога merge"
            ),
            source="rule",
            target_key=best.record.key,
        )

    # 3. Тема повторяется в нескольких документах и не конфликтует с canonical.
    approve_similarity_limit = max(
        0.0, settings.ontology_auto_merge_similarity - APPROVE_SIMILARITY_MARGIN
    )
    if (
        facts.document_count >= settings.ontology_auto_approve_min_documents
        and (best is None or best.score < approve_similarity_limit)
    ):
        return AutoReviewDecision(
            topic_key=topic.key,
            action="approve",
            confidence=round(min(0.9, 0.6 + 0.05 * facts.document_count), 3),
            reason=(
                f"Тема упомянута в {facts.document_count} документах "
                "и не совпадает с canonical-темой"
            ),
            source="rule",
        )

    # 4. Спорный случай — спрашиваем LLM.
    if provider is not None:
        review = await _ask_llm(provider, facts, similar)
        if review is not None:
            if review.confidence < settings.ontology_auto_review_min_confidence:
                return AutoReviewDecision(
                    topic_key=topic.key,
                    action="keep",
                    confidence=review.confidence,
                    reason=(
                        "Уверенность LLM ниже порога: "
                        f"{review.confidence:.2f} < "
                        f"{settings.ontology_auto_review_min_confidence:.2f}; {review.reason}"
                    ),
                    source="llm",
                )
            if review.action == "merge":
                allowed = {item.record.key for item in similar[:TOP_CANDIDATES]}
                if review.target_key not in allowed:
                    return AutoReviewDecision(
                        topic_key=topic.key,
                        action="keep",
                        confidence=review.confidence,
                        reason=(
                            f"LLM предложила merge в неизвестную тему {review.target_key!r}; "
                            f"{review.reason}"
                        ),
                        source="llm",
                    )
            return AutoReviewDecision(
                topic_key=topic.key,
                action=review.action,
                confidence=review.confidence,
                reason=review.reason,
                source="llm",
                target_key=review.target_key,
                name=review.name,
                description=review.description,
                category=review.category,
                aliases=review.aliases,
            )

    return AutoReviewDecision(
        topic_key=topic.key,
        action="keep",
        confidence=0.0,
        reason="Правила не дали решения, LLM недоступна",
        source="fallback",
    )


async def _ask_llm(
    provider: LLMProvider,
    facts: _TopicFacts,
    similar: Sequence[_SimilarTopic],
) -> _LlmReview | None:
    """Спрашивает LLM о спорной теме; при сбое возвращает None."""
    messages = [
        ChatMessage("system", REVIEW_SYSTEM_PROMPT),
        ChatMessage("user", _review_prompt(facts, similar)),
    ]
    try:
        result = await provider.generate_structured(
            messages,
            REVIEW_SCHEMA,
            schema_name=REVIEW_SCHEMA_NAME,
        )
    except LLMError as exc:
        logger.warning("LLM-ревью темы %s недоступно: %s", facts.topic.key, exc)
        return None
    except Exception:
        logger.exception("LLM-ревью темы %s завершилось ошибкой", facts.topic.key)
        return None
    return _parse_llm(result.data)


def _review_prompt(facts: _TopicFacts, similar: Sequence[_SimilarTopic]) -> str:
    """Собирает пользовательское сообщение для LLM-ревьюера."""
    lines = [
        "Проверяемая тема:",
        f"- name: {facts.topic.name}",
        f"- key: {facts.topic.key}",
        f"- description: {facts.topic.description or '—'}",
        f"- упоминаний: {facts.occurrences} в {facts.document_count} документах",
    ]
    if facts.names:
        lines.append("- варианты названия: " + "; ".join(facts.names[:10]))
    if facts.evidence:
        lines.append("- свидетельства:")
        lines.extend(f"  * {item}" for item in facts.evidence[:5])
    lines.append("")
    lines.append("Ближайшие canonical-темы:")
    if similar:
        for item in similar[:TOP_CANDIDATES]:
            lines.append(
                f"- key={item.record.key} | name={item.record.name} | "
                f"близость={item.score:.2f}"
            )
    else:
        lines.append("- нет")
    lines.append("")
    lines.append("Верни JSON по схеме без пояснений вне JSON.")
    return "\n".join(lines)


def _parse_llm(data: Any) -> _LlmReview:
    """Приводит ответ LLM к безопасному решению."""
    if not isinstance(data, dict):
        return _LlmReview(action="keep", confidence=0.0, reason="Некорректный ответ LLM")

    action = str(data.get("decision") or "keep").strip().lower()
    if action not in ("approve", "merge", "keep"):
        action = "keep"
    reason = _clean(data.get("reason"), 500) or "Без обоснования"
    target_key = _clean(data.get("target_key"), 64) or None
    if action == "merge" and target_key is None:
        action = "keep"
        reason = f"LLM выбрала merge без target_key; {reason}"

    aliases = tuple(
        alias
        for alias in (_clean(item, 200) for item in (data.get("aliases") or []) if isinstance(item, str))
        if alias
    )[:MAX_ALIASES]

    return _LlmReview(
        action=action,  # type: ignore[arg-type]
        confidence=_clamp01(data.get("confidence")),
        reason=reason,
        target_key=target_key,
        name=_clean(data.get("name"), 120) or None,
        description=_clean(data.get("description"), 2000) or None,
        category=_clean(data.get("category"), 50) or None,
        aliases=aliases,
    )


async def _apply(
    session: AsyncSession,
    facts: _TopicFacts,
    decision: AutoReviewDecision,
) -> None:
    """Применяет решение и фиксирует его в аудите."""
    topic = facts.topic
    details = {
        "decision": decision.action,
        "source": decision.source,
        "confidence": decision.confidence,
        "reason": decision.reason,
        "occurrences": facts.occurrences,
        "documents": facts.document_count,
    }
    if decision.target_key:
        details["target_key"] = decision.target_key

    if decision.action == "merge":
        if not decision.target_key:
            raise ReviewError("Для merge не указана целевая тема")
        # Метод сопоставления меняем до merge: после переноса навыки уже
        # принадлежат целевой теме и их нельзя отличить от «родных».
        await _set_match_method(session, topic.id, "auto_merge")
        await merge_topics(
            session,
            topic.key,
            decision.target_key,
            actor=AUTO_ACTOR,
            details=details,
        )
    elif decision.action == "approve":
        await _enrich_topic(session, topic, decision)
        await approve_topic(session, topic.key, actor=AUTO_ACTOR, details=details)
        await _set_match_method(session, topic.id, "auto_approve")
    else:
        record_review_action(session, "keep", topic, actor=AUTO_ACTOR, details=details)

    topic.auto_reviewed_at = datetime.now(UTC)
    topic.auto_review_decision = decision.action
    topic.auto_review_confidence = decision.confidence
    topic.auto_reviewed_occurrences = facts.occurrences
    await session.flush()


async def _set_match_method(
    session: AsyncSession,
    topic_id: uuid.UUID,
    method: str,
) -> None:
    """Обновляет метод сопоставления у навыков, пришедших из provisional-темы."""
    for model in (ResumeSkill, VacancySkill):
        await session.execute(
            update(model)
            .where(model.topic_id == topic_id, model.match_method == "provisional")
            .values(match_method=method)
        )


async def _enrich_topic(
    session: AsyncSession,
    topic: Topic,
    decision: AutoReviewDecision,
) -> None:
    """Дополняет тему названием, описанием и алиасами из LLM-ответа."""
    if decision.name:
        topic.name = decision.name
    if decision.description:
        topic.description = decision.description
    if decision.category:
        topic.category = decision.category
    if not decision.aliases:
        return

    existing = set((await session.scalars(select(TopicAlias.normalized_alias))).all())
    current_aliases = list(topic.aliases or [])
    for alias in decision.aliases:
        normalized = normalize_name(alias)
        if not normalized or normalized in existing:
            continue
        session.add(
            TopicAlias(
                topic_id=topic.id,
                alias=alias,
                normalized_alias=normalized,
                source="auto",
                status="active",
            )
        )
        existing.add(normalized)
        if alias not in current_aliases:
            current_aliases.append(alias)
    topic.aliases = current_aliases


async def _load_facts(session: AsyncSession, topic: Topic) -> _TopicFacts:
    """Собирает названия, упоминания и свидетельства по теме."""
    candidates = (
        await session.scalars(
            select(TopicCandidate).where(TopicCandidate.topic_id == topic.id)
        )
    ).all()
    aliases = (
        await session.scalars(
            select(TopicAlias).where(
                TopicAlias.topic_id == topic.id,
                TopicAlias.status == "active",
            )
        )
    ).all()

    names: list[str] = []

    def add_name(value: str | None) -> None:
        cleaned = _clean(value, 200)
        if cleaned and cleaned not in names:
            names.append(cleaned)

    add_name(topic.name)
    for candidate in candidates:
        add_name(candidate.name)
    for alias in aliases:
        add_name(alias.alias)

    sources: set[tuple[str, str]] = set()
    evidence: list[str] = []
    occurrences = 0
    for candidate in candidates:
        occurrences += max(1, candidate.occurrences or 1)
        for source in candidate.sources or []:
            if not isinstance(source, dict):
                continue
            source_type = source.get("type")
            source_id = source.get("id")
            if source_type and source_id:
                sources.add((str(source_type), str(source_id)))
            text = _clean(source.get("evidence"), 240)
            if text and text not in evidence:
                evidence.append(text)

    return _TopicFacts(
        topic=topic,
        names=tuple(names),
        document_count=len(sources),
        occurrences=max(1, occurrences),
        evidence=tuple(evidence),
    )


def _needs_review(topic: Topic, occurrences: int) -> bool:
    """Проверяет, появились ли новые данные с прошлого авто-ревью."""
    if topic.auto_reviewed_at is None:
        return True
    if topic.auto_review_decision != "keep":
        return False
    return occurrences > (topic.auto_reviewed_occurrences or 0)


async def _rank_similar(
    facts: _TopicFacts,
    index: TopicIndex,
    embedder: EmbeddingProvider | None,
) -> list[_SimilarTopic]:
    """Ранжирует canonical-темы по близости к проверяемой теме."""
    records = list(index.topics)
    if not records:
        return []

    if embedder is not None and embedder.available:
        texts = [_similarity_text(facts), *(record.embedding_text() for record in records)]
        try:
            vectors = await embedder.embed(texts)
        except Exception:
            logger.warning("Эмбеддинги для авто-ревью недоступны, используется fuzzy", exc_info=True)
            vectors = []
        if len(vectors) == len(records) + 1 and vectors[0]:
            scored = [
                (record, cosine_similarity(vectors[0], vector))
                for record, vector in zip(records, vectors[1:], strict=True)
            ]
            return _sorted_similar(scored)

    scored = []
    normalized_names = [normalize_name(name) for name in facts.names if normalize_name(name)]
    for record in records:
        targets = (record.key, record.name, *record.aliases)
        best = 0.0
        for normalized in normalized_names:
            for target in targets:
                score = SequenceMatcher(None, normalized, normalize_name(target)).ratio()
                best = max(best, score)
        scored.append((record, best))
    return _sorted_similar(scored)


def _similarity_text(facts: _TopicFacts) -> str:
    """Текст проверяемой темы для эмбеддингов."""
    parts = [*facts.names[:5], facts.topic.description or ""]
    return ". ".join(part for part in parts if part)


def _sorted_similar(
    scored: Sequence[tuple[TopicRecord, float]],
) -> list[_SimilarTopic]:
    """Сортирует темы по убыванию близости."""
    return [
        _SimilarTopic(record=record, score=round(score, 3))
        for record, score in sorted(scored, key=lambda item: item[1], reverse=True)
    ]


def _clean(value: Any, limit: int) -> str:
    """Схлопывает пробелы и обрезает строку до лимита поля БД."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _clamp01(value: Any) -> float:
    """Приводит уверенность к диапазону 0..1."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))
