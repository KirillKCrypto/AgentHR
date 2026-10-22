"""Интерфейс слоя эмбеддингов.

Эмбеддинги используются для семантического сопоставления навыков темам
онтологии. Провайдер локальный (ONNX, без внешних сервисов) и опциональный:
если он недоступен, нормализация продолжает работать по точному совпадению,
алиасам и нечёткому сравнению.
"""

import math
from collections.abc import Sequence
from typing import Protocol


class EmbeddingError(Exception):
    """Ошибка слоя эмбеддингов."""


class EmbeddingConfigurationError(EmbeddingError):
    """Некорректная конфигурация провайдера эмбеддингов."""


class EmbeddingProvider(Protocol):
    """Провайдер векторных представлений текста."""

    @property
    def available(self) -> bool:
        """Готов ли провайдер отдавать векторы."""
        ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Возвращает вектор для каждого текста (в том же порядке)."""
        ...


class NullEmbeddingProvider:
    """Заглушка: эмбеддингов нет, этап семантического сопоставления пропускается."""

    @property
    def available(self) -> bool:
        return False

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return []


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Косинусная близость двух векторов; 0.0 при нулевых или разной длины."""
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
