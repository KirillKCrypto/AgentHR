"""Определение уровня вакансии для сложности интервью."""

import re
from collections.abc import Sequence

_LEVEL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("lead", r"\b(lead|principal|staff|лид|ведущий)\b"),
    ("senior", r"\b(senior|sr|сеньор|старший)\b"),
    ("middle", r"\b(middle|mid|мидл|средний)\b"),
    ("junior", r"\b(junior|intern|trainee|джуниор|стажёр|стажер)\b"),
)


def normalize_level(value: str | None) -> str | None:
    """Приводит свободный текст к уровню junior/middle/senior/lead."""
    text = (value or "").strip().lower()
    if not text:
        return None
    for level, pattern in _LEVEL_PATTERNS:
        if re.search(pattern, text):
            return level
    return None


def resolve_vacancy_level(
    llm_level: str | None,
    title: str | None,
    raw_text: str | None,
) -> str | None:
    """Выбирает уровень: название вакансии важнее ответа модели и текста.

    Модель иногда возвращает middle для вакансии с «Senior» в заголовке.
    Заголовок — самый надёжный сигнал, поэтому проверяется первым.
    """
    for source in (title, llm_level, raw_text):
        level = normalize_level(source)
        if level is not None:
            return level
    return None


def level_band(level: str | None, required_levels: Sequence[int]) -> str | None:
    """Сводит уровень к диапазону сложности; без уровня — по медиане требований."""
    normalized = normalize_level(level)
    if normalized in ("senior", "lead"):
        return "senior_lead"
    if normalized in ("junior", "middle"):
        return "junior_middle"
    if not required_levels:
        return None
    ordered = sorted(required_levels)
    median = ordered[len(ordered) // 2]
    return "junior_middle" if median < 70 else "senior_lead"
