"""Детерминированный мок-провайдер эмбеддингов (без сети и моделей).

Вектор строится из хешей слов текста: у текстов с общими словами векторы
ближе друг к другу. Этого достаточно, чтобы проверять логику сопоставления
в тестах, не загружая реальную модель.
"""

import hashlib
import math
import re
from collections.abc import Sequence

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class MockEmbeddingProvider:
    """Мок-провайдер: одинаковый текст — одинаковый вектор."""

    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    @property
    def available(self) -> bool:
        return True

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for token in set(_TOKEN_RE.findall(text.lower())):
            digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
            vector[int(digest, 16) % self._dim] = 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if not norm:
            return vector
        return [value / norm for value in vector]
