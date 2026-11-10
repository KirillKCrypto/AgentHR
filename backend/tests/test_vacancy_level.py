"""Определение уровня вакансии и диапазона сложности."""

from app.services.vacancy_level import level_band, normalize_level, resolve_vacancy_level


def test_normalize_level_recognizes_titles() -> None:
    """Уровень распознаётся в английских и русских названиях."""
    assert normalize_level("Senior Python разработчик") == "senior"
    assert normalize_level("ML Engineer Senior") == "senior"
    assert normalize_level("Team Lead") == "lead"
    assert normalize_level("Junior Backend") == "junior"
    assert normalize_level("Мидл-разработчик") == "middle"
    assert normalize_level("Ведущий инженер") == "lead"
    assert normalize_level("Backend Engineer") is None


def test_title_beats_wrong_llm_level() -> None:
    """«Senior» в заголовке важнее ошибочного middle от модели."""
    assert (
        resolve_vacancy_level(
            "middle",
            "Senior Python разработчик",
            "Требования: 6+ лет Python, PostgreSQL.",
        )
        == "senior"
    )


def test_level_falls_back_to_llm_and_text() -> None:
    """Без уровня в заголовке используются ответ модели или текст."""
    assert resolve_vacancy_level("junior", "Backend", "Python") == "junior"
    assert resolve_vacancy_level(None, "Backend", "Senior role") == "senior"
    assert resolve_vacancy_level(None, "Backend", "Python") is None


def test_level_band_uses_median_without_level() -> None:
    """Без уровня диапазон оценивается по медиане требований."""
    assert level_band("senior", [60]) == "senior_lead"
    assert level_band("junior", [90]) == "junior_middle"
    assert level_band(None, [40, 50, 60]) == "junior_middle"
    assert level_band(None, [70, 80, 90]) == "senior_lead"
    assert level_band(None, []) is None
