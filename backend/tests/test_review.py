"""Расписание повторения тем."""

from datetime import UTC, datetime, timedelta

from app.services.review import next_review


def test_review_interval_depends_on_score() -> None:
    """Слабые темы возвращаются раньше сильных."""
    weak_due, weak_days = next_review(40)
    strong_due, strong_days = next_review(90, previous_days=7)

    assert weak_days == 1
    assert strong_days >= 7
    assert weak_due > datetime.now(UTC)
    assert strong_due > weak_due + timedelta(days=3)


def test_review_interval_is_capped() -> None:
    """Интервал не растёт бесконечно."""
    _, days = next_review(100, previous_days=14)
    assert days == 14


def test_review_interval_accepts_missing_previous_days() -> None:
    """Новое состояние без интервала не роняет расчёт (регресс 500)."""
    _, days = next_review(90, previous_days=None)
    assert days == 7
