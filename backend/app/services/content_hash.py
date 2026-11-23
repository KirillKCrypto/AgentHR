"""Нормализация текста документов и стабильный хеш содержимого."""

import hashlib
import re

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def normalize_content(text: str) -> str:
    """Схлопывает пробелы и приводит регистр к нижнему."""
    return _WHITESPACE_RE.sub(" ", text.strip()).casefold()


def content_hash(text: str) -> str:
    """SHA-256 от нормализованного текста: одинаковый текст даёт один хеш."""
    return hashlib.sha256(normalize_content(text).encode("utf-8")).hexdigest()
