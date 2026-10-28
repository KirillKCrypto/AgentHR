"""Тесты нормализации навыков к онтологии (без БД)."""

import uuid

import pytest

from app.embeddings import MockEmbeddingProvider, NullEmbeddingProvider
from app.services.normalization import (
    SkillMatcher,
    TopicIndex,
    TopicRecord,
    normalize_name,
)

TOPICS = (
    TopicRecord(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        key="sql",
        name="SQL",
        description="язык SQL: SELECT, JOIN, GROUP BY, индексы, планы запросов",
        aliases=("язык запросов", "postgresql", "t-sql"),
    ),
    TopicRecord(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        key="testing",
        name="Тестирование и качество кода",
        description="юнит-тесты, pytest, фикстуры, моки, покрытие кода",
        aliases=("тестирование", "unit testing"),
    ),
    TopicRecord(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        key="oop",
        name="ООП и паттерны проектирования",
        description="классы, наследование, SOLID, паттерны проектирования",
        aliases=("ооп", "design patterns", "паттерны проектирования"),
    ),
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  PostgreSQL  ", "postgresql"),
        ("ООП", "oop"),
        ("Unit-Testing", "unit testing"),
        ("С++, C#", "cpp csharp"),
        ("Python 3", "python 3"),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    """Название нормализуется: регистр, омоглифы, пунктуация, пробелы."""
    assert normalize_name(raw) == expected


def test_index_finds_exact_by_key_and_name() -> None:
    """Тема находится по ключу и по названию."""
    index = TopicIndex(TOPICS)
    assert index.find_exact("sql").key == "sql"
    assert index.find_exact("Тестирование и качество кода").key == "testing"
    assert index.find_exact("несуществующая") is None


def test_index_finds_alias() -> None:
    """Тема находится по алиасу (в том числе при латинице вместо кириллицы)."""
    index = TopicIndex(TOPICS)
    assert index.find_alias("Design Patterns").key == "oop"
    assert index.find_alias("postgresql").key == "sql"
    assert index.find_alias("OOP").key == "oop"
    assert index.find_alias("что-то другое") is None


def test_index_fuzzy_finds_near_match() -> None:
    """Нечёткое совпадение находит близкое по написанию название."""
    index = TopicIndex(TOPICS)
    topic, score = index.find_fuzzy("паттерн проектирования")
    assert topic is not None
    assert topic.key == "oop"
    assert score >= 0.85


def test_index_fuzzy_rejects_unrelated() -> None:
    """Совсем другой навык не сопоставляется нечётко."""
    index = TopicIndex(TOPICS)
    topic, _ = index.find_fuzzy("kafka")
    assert topic is None


async def test_matcher_prefers_exact_then_alias_then_fuzzy() -> None:
    """Порядок сопоставления: exact → alias → fuzzy."""
    matcher = SkillMatcher(TopicIndex(TOPICS))
    assert (await matcher.match("SQL")).method == "exact"
    assert (await matcher.match("PostgreSQL")).method == "alias"
    assert (await matcher.match("паттерн проектирования")).method == "fuzzy"


async def test_matcher_reports_unmatched_skill() -> None:
    """Несопоставленный навык не подгоняется под тему."""
    matcher = SkillMatcher(TopicIndex(TOPICS))
    match = await matcher.match("Kafka")
    assert match.matched is False
    assert match.method == "none"
    assert match.topic_id is None


async def test_matcher_uses_embeddings_when_available() -> None:
    """Совпадение по смыслу работает, когда эмбеддер доступен."""
    compact = TopicIndex(
        (
            TopicRecord(
                id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
                key="sql",
                name="SQL",
                description="select join",
            ),
            TopicRecord(
                id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
                key="testing",
                name="Тесты",
                description="pytest fixtures",
            ),
        )
    )
    matcher = SkillMatcher(compact, MockEmbeddingProvider(), embedding_threshold=0.35)
    match = await matcher.match("select join")
    assert match.method == "embedding"
    assert match.topic_key == "sql"
    assert match.score >= 0.35


async def test_matcher_skips_embeddings_when_unavailable() -> None:
    """Без эмбеддера семантический этап пропускается, а не ломает сопоставление."""
    matcher = SkillMatcher(TopicIndex(TOPICS), NullEmbeddingProvider())
    match = await matcher.match("select join индексы")
    assert match.method == "none"


async def test_matcher_match_many_is_consistent() -> None:
    """Пакетное сопоставление даёт те же результаты, что и по одному."""
    matcher = SkillMatcher(TopicIndex(TOPICS))
    names = ["SQL", "PostgreSQL", "Kafka", "паттерн проектирования"]
    batch = await matcher.match_many(names)
    single = [await matcher.match(name) for name in names]
    assert [(m.method, m.topic_id) for m in batch] == [(m.method, m.topic_id) for m in single]


async def test_matcher_handles_empty_name() -> None:
    """Пустое название не роняет сопоставитель."""
    matcher = SkillMatcher(TopicIndex(TOPICS))
    match = await matcher.match("   ")
    assert match.matched is False
