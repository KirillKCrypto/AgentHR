"""Расписание повторения тем."""

from datetime import UTC, datetime, timedelta

MAX_INTERVAL_DAYS = 14


def next_review(score: float, previous_days: int | None = 1) -> tuple[datetime, int]:
    """Выбирает интервал по качеству ответа и возвращает дату повторения."""
    previous = max(1, previous_days or 1)
    if score < 50:
        interval = 1
    elif score < 70:
        interval = 3
    elif score < 85:
        interval = 7
    else:
        interval = max(previous * 2, 7)
    interval = min(MAX_INTERVAL_DAYS, max(1, interval))
    return datetime.now(UTC) + timedelta(days=interval), interval
