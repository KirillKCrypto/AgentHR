"""Фабрика провайдера эмбеддингов по настройкам приложения."""

from app.core.config import Settings, get_settings
from app.embeddings.base import (
    EmbeddingConfigurationError,
    EmbeddingProvider,
    NullEmbeddingProvider,
)
from app.embeddings.local import LocalEmbeddingProvider
from app.embeddings.mock import MockEmbeddingProvider


def create_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Создаёт провайдера эмбеддингов по настройкам (по умолчанию — без эмбеддингов)."""
    current = settings or get_settings()
    provider = (current.embedding_provider or "none").strip().lower()

    if provider in ("", "none", "off", "disabled"):
        return NullEmbeddingProvider()
    if provider == "mock":
        return MockEmbeddingProvider()
    if provider == "local":
        return LocalEmbeddingProvider(
            model_name=current.embedding_model,
            cache_dir=current.embedding_cache_dir,
        )

    raise EmbeddingConfigurationError(f"Неизвестный EMBEDDING_PROVIDER: {provider!r}")
