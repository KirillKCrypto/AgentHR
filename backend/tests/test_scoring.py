"""Детерминированный расчёт оценки ответа по рубрике."""

from app.services.interview import _score_from_evaluation


def _assessment(status: str, point: str = "пункт") -> dict[str, str]:
    """Один эталонный пункт в ответе модели."""
    return {"point": point, "status": status, "evidence": "цитата"}


def test_rubric_sums_dimensions() -> None:
    """Итог — верность + покрытие + глубина."""
    result = _score_from_evaluation(
        {
            "correctness": 45,
            "coverage": 30,
            "depth": 15,
            "relevance": "on_topic",
            "point_assessments": [_assessment("covered", "a"), _assessment("covered", "b")],
            "critical_errors": [],
            "covered_points": [],
            "missed_points": [],
            "feedback_brief": "Хорошо.",
        }
    )

    assert result["score"] == 90
    assert result["breakdown"]["coverage"] == 30


def test_main_idea_without_details_is_not_70() -> None:
    """Короткий верный ответ без деталей не получает 70+."""
    result = _score_from_evaluation(
        {
            "correctness": 30,
            "coverage": 10,
            "depth": 4,
            "relevance": "on_topic",
            "point_assessments": [_assessment("partial"), _assessment("missed")],
            "critical_errors": [],
            "covered_points": [],
            "missed_points": [],
            "feedback_brief": "Есть суть, нет деталей.",
        }
    )

    assert result["score"] < 70


def test_off_topic_is_capped() -> None:
    """Ответ не по вопросу не может получить больше 20."""
    result = _score_from_evaluation(
        {
            "correctness": 40,
            "coverage": 20,
            "depth": 10,
            "relevance": "off_topic",
            "point_assessments": [],
            "critical_errors": [],
            "covered_points": [],
            "missed_points": [],
            "feedback_brief": "Не по вопросу.",
        }
    )

    assert result["score"] == 20


def test_critical_error_caps_score() -> None:
    """Фактическая ошибка ограничивает оценку 45."""
    result = _score_from_evaluation(
        {
            "correctness": 45,
            "coverage": 25,
            "depth": 15,
            "relevance": "on_topic",
            "point_assessments": [],
            "critical_errors": ["перепутан уровень изоляции"],
            "covered_points": [],
            "missed_points": [],
            "feedback_brief": "Есть критическая ошибка.",
        }
    )

    assert result["score"] == 45


def test_legacy_score_is_still_supported() -> None:
    """Старый формат ответа модели не ломает интервью."""
    result = _score_from_evaluation({"score": 80, "feedback_brief": "Ок."})

    assert result["score"] == 80
    assert result["breakdown"] == {"legacy_score": 80}


def test_supporting_points_weigh_less() -> None:
    """Второстепенные эталонные пункты не штрафуют так же, как essential."""
    result = _score_from_evaluation(
        {
            "correctness": 48,
            "depth": 6,
            "relevance": "on_topic",
            "point_assessments": [
                {
                    "point": "суть",
                    "status": "covered",
                    "evidence": "цитата",
                    "importance": "essential",
                },
                {
                    "point": "functools.wraps",
                    "status": "missed",
                    "evidence": "",
                    "importance": "supporting",
                },
            ],
            "critical_errors": [],
            "covered_points": [],
            "missed_points": [],
            "feedback_brief": "Верно, но без деталей.",
        }
    )

    assert result["breakdown"]["coverage"] >= 20
    assert result["score"] >= 70
