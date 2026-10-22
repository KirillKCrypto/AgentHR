"""Сервисный слой AgentHR: анализ вакансий и резюме, нормализация навыков."""

from app.services.evaluation import precision_recall
from app.services.normalization import (
    SkillMatcher,
    TopicIndex,
    TopicMatch,
    TopicRecord,
    normalize_name,
)
from app.services.topics import (
    create_skill_matcher,
    load_packaged_topic_index,
    load_topic_index,
)

__all__ = [
    "SkillMatcher",
    "TopicIndex",
    "TopicMatch",
    "TopicRecord",
    "create_skill_matcher",
    "load_packaged_topic_index",
    "load_topic_index",
    "normalize_name",
    "precision_recall",
]
