"""Интеграционный тест локального ONNX-эмбеддера.

Пропускается, если пакет `fastembed` не установлен (uv sync --extra embeddings)
или модель недоступна в офлайн-режиме.
"""

import importlib.util

import pytest

from app.core.config import Settings
from app.embeddings import create_embedding_provider
from app.services.normalization import SkillMatcher
from app.services.topics import load_packaged_topic_index

fastembed_installed = importlib.util.find_spec("fastembed") is not None

pytestmark = pytest.mark.skipif(
    not fastembed_installed,
    reason="fastembed не установлен — поставьте: uv sync --extra embeddings",
)


async def _matcher() -> SkillMatcher:
    """Сопоставитель с локальным эмбеддером."""
    provider = create_embedding_provider(
        Settings(embedding_provider="local", embedding_cache_dir=".cache/fastembed")
    )
    if not provider.available:
        pytest.skip(f"локальный эмбеддер недоступен: {getattr(provider, 'error', None)}")
    return SkillMatcher(load_packaged_topic_index(), provider, embedding_threshold=0.35)


async def test_local_provider_is_available() -> None:
    """Локальный эмбеддер загружается и отдаёт векторы."""
    provider = create_embedding_provider(
        Settings(embedding_provider="local", embedding_cache_dir=".cache/fastembed")
    )
    if not provider.available:
        pytest.skip(f"локальный эмбеддер недоступен: {getattr(provider, 'error', None)}")

    vectors = await provider.embed(["Python", "SQL"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 384


async def test_local_embeddings_match_expected_topics() -> None:
    """Смысловое сопоставление работает на русском языке."""
    matcher = await _matcher()
    matches = await matcher.match_many(
        ["GitHub Actions", "нормализация схемы БД", "Kafka", "Fortran"]
    )
    assert matches[0].topic_key == "cicd"
    assert matches[0].method == "alias"
    assert matches[1].topic_key == "databases"
    assert matches[1].method == "embedding"
    # В ontology v2 Kafka — отдельная canonical-тема
    assert matches[2].topic_key == "kafka"
    assert matches[2].matched is True
    # Навык вне онтологии не подгоняется под тему
    assert matches[3].matched is False
