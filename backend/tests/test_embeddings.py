"""Тесты слоя эмбеддингов (без сети и без моделей)."""

import math

import pytest

from app.core.config import Settings
from app.embeddings import (
    EmbeddingConfigurationError,
    LocalEmbeddingProvider,
    MockEmbeddingProvider,
    NullEmbeddingProvider,
    cosine_similarity,
    create_embedding_provider,
)


def test_cosine_similarity_of_equal_vectors() -> None:
    """Одинаковые векторы дают близость 1."""
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_of_orthogonal_vectors() -> None:
    """Перпендикулярные векторы дают близость 0."""
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_handles_degenerate_input() -> None:
    """Нулевые векторы и разная длина дают 0, а не исключение."""
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([], []) == 0.0


async def test_mock_provider_is_deterministic() -> None:
    """Мок-провайдер отдаёт одинаковый вектор для одинакового текста."""
    provider = MockEmbeddingProvider()
    first = await provider.embed(["PostgreSQL"])
    second = await provider.embed(["PostgreSQL"])
    assert provider.available is True
    assert first == second
    assert len(first[0]) == 64


async def test_mock_provider_similarity_follows_shared_words() -> None:
    """Тексты с общими словами дают более близкие векторы."""
    provider = MockEmbeddingProvider()
    vectors = await provider.embed(
        ["select join запросы", "select join индексы", "котики и собачки"]
    )
    close = cosine_similarity(vectors[0], vectors[1])
    far = cosine_similarity(vectors[0], vectors[2])
    assert close > far


async def test_null_provider_is_unavailable() -> None:
    """Заглушка сообщает, что эмбеддингов нет, и не падает."""
    provider = NullEmbeddingProvider()
    assert provider.available is False
    assert await provider.embed(["что угодно"]) == []


def test_factory_returns_null_by_default() -> None:
    """По умолчанию эмбеддеры выключены."""
    provider = create_embedding_provider(Settings(embedding_provider="none"))
    assert isinstance(provider, NullEmbeddingProvider)


def test_factory_returns_mock() -> None:
    """Для тестов доступен мок-провайдер."""
    provider = create_embedding_provider(Settings(embedding_provider="mock"))
    assert isinstance(provider, MockEmbeddingProvider)


def test_factory_rejects_unknown_provider() -> None:
    """Неизвестный провайдер — понятная ошибка конфигурации."""
    with pytest.raises(EmbeddingConfigurationError):
        create_embedding_provider(Settings(embedding_provider="unknown"))


def test_local_provider_is_unavailable_without_fastembed(monkeypatch) -> None:
    """Без установленного fastembed локальный провайдер недоступен, но не падает."""
    import sys

    # РРјРёС‚РёСЂСѓРµРј РѕС‚СЃСѓС‚СЃС‚РІРёРµ РїР°РєРµС‚Р°: РёРјРїРѕСЂС‚ fastembed Р·Р°РІРµСЂС€Р°РµС‚СЃСЏ ImportError
    monkeypatch.setitem(sys.modules, "fastembed", None)
    provider = LocalEmbeddingProvider(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    assert provider.available is False
    assert provider.error is not None
    assert "fastembed" in provider.error


def test_mock_provider_vector_is_normalized() -> None:
    """Векторы мока нормированы — косинус корректен."""
    import asyncio

    vector = asyncio.run(MockEmbeddingProvider().embed(["нормализация вектора"]))[0]
    norm = math.sqrt(sum(value * value for value in vector))
    assert norm == pytest.approx(1.0)

