"""Слой эмбеддингов AgentHR: локальные векторы для нормализации навыков."""

from app.embeddings.base import (
    EmbeddingConfigurationError,
    EmbeddingError,
    EmbeddingProvider,
    NullEmbeddingProvider,
    cosine_similarity,
)
from app.embeddings.factory import create_embedding_provider
from app.embeddings.local import LocalEmbeddingProvider
from app.embeddings.mock import MockEmbeddingProvider

__all__ = [
    "EmbeddingConfigurationError",
    "EmbeddingError",
    "EmbeddingProvider",
    "LocalEmbeddingProvider",
    "MockEmbeddingProvider",
    "NullEmbeddingProvider",
    "cosine_similarity",
    "create_embedding_provider",
]
