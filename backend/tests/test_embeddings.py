"""РўРµСЃС‚С‹ СЃР»РѕСЏ СЌРјР±РµРґРґРёРЅРіРѕРІ (Р±РµР· СЃРµС‚Рё Рё Р±РµР· РјРѕРґРµР»РµР№)."""

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
    """РћРґРёРЅР°РєРѕРІС‹Рµ РІРµРєС‚РѕСЂС‹ РґР°СЋС‚ Р±Р»РёР·РѕСЃС‚СЊ 1."""
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_of_orthogonal_vectors() -> None:
    """РџРµСЂРїРµРЅРґРёРєСѓР»СЏСЂРЅС‹Рµ РІРµРєС‚РѕСЂС‹ РґР°СЋС‚ Р±Р»РёР·РѕСЃС‚СЊ 0."""
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_handles_degenerate_input() -> None:
    """РќСѓР»РµРІС‹Рµ РІРµРєС‚РѕСЂС‹ Рё СЂР°Р·РЅР°СЏ РґР»РёРЅР° РґР°СЋС‚ 0, Р° РЅРµ РёСЃРєР»СЋС‡РµРЅРёРµ."""
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([], []) == 0.0


async def test_mock_provider_is_deterministic() -> None:
    """РњРѕРє-РїСЂРѕРІР°Р№РґРµСЂ РѕС‚РґР°С‘С‚ РѕРґРёРЅР°РєРѕРІС‹Р№ РІРµРєС‚РѕСЂ РґР»СЏ РѕРґРёРЅР°РєРѕРІРѕРіРѕ С‚РµРєСЃС‚Р°."""
    provider = MockEmbeddingProvider()
    first = await provider.embed(["PostgreSQL"])
    second = await provider.embed(["PostgreSQL"])
    assert provider.available is True
    assert first == second
    assert len(first[0]) == 64


async def test_mock_provider_similarity_follows_shared_words() -> None:
    """РўРµРєСЃС‚С‹ СЃ РѕР±С‰РёРјРё СЃР»РѕРІР°РјРё РґР°СЋС‚ Р±РѕР»РµРµ Р±Р»РёР·РєРёРµ РІРµРєС‚РѕСЂС‹."""
    provider = MockEmbeddingProvider()
    vectors = await provider.embed(
        ["select join Р·Р°РїСЂРѕСЃС‹", "select join РёРЅРґРµРєСЃС‹", "РєРѕС‚РёРєРё Рё СЃРѕР±Р°С‡РєРё"]
    )
    close = cosine_similarity(vectors[0], vectors[1])
    far = cosine_similarity(vectors[0], vectors[2])
    assert close > far


async def test_null_provider_is_unavailable() -> None:
    """Р—Р°РіР»СѓС€РєР° СЃРѕРѕР±С‰Р°РµС‚, С‡С‚Рѕ СЌРјР±РµРґРґРёРЅРіРѕРІ РЅРµС‚, Рё РЅРµ РїР°РґР°РµС‚."""
    provider = NullEmbeddingProvider()
    assert provider.available is False
    assert await provider.embed(["С‡С‚Рѕ СѓРіРѕРґРЅРѕ"]) == []


def test_factory_returns_null_by_default() -> None:
    """РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ СЌРјР±РµРґРґРµСЂС‹ РІС‹РєР»СЋС‡РµРЅС‹."""
    provider = create_embedding_provider(Settings(embedding_provider="none"))
    assert isinstance(provider, NullEmbeddingProvider)


def test_factory_returns_mock() -> None:
    """Р”Р»СЏ С‚РµСЃС‚РѕРІ РґРѕСЃС‚СѓРїРµРЅ РјРѕРє-РїСЂРѕРІР°Р№РґРµСЂ."""
    provider = create_embedding_provider(Settings(embedding_provider="mock"))
    assert isinstance(provider, MockEmbeddingProvider)


def test_factory_rejects_unknown_provider() -> None:
    """РќРµРёР·РІРµСЃС‚РЅС‹Р№ РїСЂРѕРІР°Р№РґРµСЂ вЂ” РїРѕРЅСЏС‚РЅР°СЏ РѕС€РёР±РєР° РєРѕРЅС„РёРіСѓСЂР°С†РёРё."""
    with pytest.raises(EmbeddingConfigurationError):
        create_embedding_provider(Settings(embedding_provider="unknown"))


def test_local_provider_is_unavailable_without_fastembed(monkeypatch) -> None:
    """Р‘РµР· СѓСЃС‚Р°РЅРѕРІР»РµРЅРЅРѕРіРѕ fastembed Р»РѕРєР°Р»СЊРЅС‹Р№ РїСЂРѕРІР°Р№РґРµСЂ РЅРµРґРѕСЃС‚СѓРїРµРЅ, РЅРѕ РЅРµ РїР°РґР°РµС‚."""
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
    """Р’РµРєС‚РѕСЂС‹ РјРѕРєР° РЅРѕСЂРјРёСЂРѕРІР°РЅС‹ вЂ” РєРѕСЃРёРЅСѓСЃ РєРѕСЂСЂРµРєС‚РµРЅ."""
    import asyncio

    vector = asyncio.run(MockEmbeddingProvider().embed(["РЅРѕСЂРјР°Р»РёР·Р°С†РёСЏ РІРµРєС‚РѕСЂР°"]))[0]
    norm = math.sqrt(sum(value * value for value in vector))
    assert norm == pytest.approx(1.0)

