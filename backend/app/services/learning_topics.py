"""Учебные и служебные темы онтологии."""

from app.models import Topic

# Служебная тема авто-ревью: собирает общий шум, а не отдельный навык.
NON_LEARNING_TOPIC_KEYS: frozenset[str] = frozenset({"other-auto-review"})


def is_learning_topic(topic: Topic) -> bool:
    """Можно ли строить по теме план, тест и интервью."""
    return topic.key not in NON_LEARNING_TOPIC_KEYS
