"""Метрики качества извлечения навыков (precision / recall / F1).

Используются и в тестах (на записанных ответах модели), и в eval-скрипте
для живого LLM.
"""

from collections.abc import Iterable

from app.services.normalization import normalize_name


def normalize_set(names: Iterable[str]) -> set[str]:
    """Множество нормализованных названий навыков."""
    return {normalize_name(name) for name in names if normalize_name(name)}


def precision_recall(expected: Iterable[str], actual: Iterable[str]) -> tuple[float, float, float]:
    """Считает precision, recall и F1 по множествам нормализованных названий."""
    expected_set = normalize_set(expected)
    actual_set = normalize_set(actual)
    if not expected_set and not actual_set:
        return 1.0, 1.0, 1.0
    true_positive = len(expected_set & actual_set)
    precision = true_positive / len(actual_set) if actual_set else 0.0
    recall = true_positive / len(expected_set) if expected_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def format_metrics(label: str, precision: float, recall: float, f1: float) -> str:
    """Строка отчёта по метрикам."""
    return f"{label}: precision={precision:.3f} recall={recall:.3f} f1={f1:.3f}"
