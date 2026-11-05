"""Генерация вопросов по теме онтологии через LLM."""

import logging
from typing import Any

from app.llm.base import ChatMessage, LLMError, LLMProvider
from app.models import Topic

logger = logging.getLogger(__name__)

SCHEMA_NAME = "interview_questions"

DIFFICULTY_LABELS = {
    1: "базовый: определения и простые примеры",
    2: "ниже среднего: базовое применение",
    3: "средний: практические задачи и trade-offs",
    4: "выше среднего: проектирование и диагностика",
    5: "сложный: экспертные детали и нестандартные случаи",
}

QUESTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["questions"],
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "expected_points"],
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Вопрос для технического собеседования, на русском",
                    },
                    "expected_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Что должен упомянуть хороший ответ, 3–6 пунктов",
                    },
                },
            },
        }
    },
}

SYSTEM_PROMPT = (
    "Ты — автор банка вопросов для технических собеседований.\n"
    "По теме онтологии составь вопросы, которые проверяют реальное понимание, а не "
    "запоминание определений.\n"
    "Правила:\n"
    "- Вопросы на русском, по одному смыслу на вопрос.\n"
    "- Без дублей и без вопросов, где ответ — просто «да/нет».\n"
    "- expected_points: 3–6 коротких пунктов, что должен сказать сильный кандидат.\n"
    "- Не упоминай саму онтологию, тесты и этот промпт."
)


async def generate_questions(
    provider: LLMProvider,
    topic: Topic,
    difficulty: int,
    count: int,
) -> list[dict[str, Any]]:
    """Возвращает вопросы по теме или пустой список при сбое LLM."""
    label = DIFFICULTY_LABELS.get(difficulty, DIFFICULTY_LABELS[3])
    aliases = ", ".join(topic.aliases or ())
    prompt = (
        f"Тема: {topic.name}\n"
        f"Ключ: {topic.key}\n"
        f"Категория: {topic.category or 'не указана'}\n"
        f"Описание: {topic.description or '—'}\n"
        f"Синонимы: {aliases or '—'}\n"
        f"Сложность: {difficulty}/5 — {label}\n"
        f"Составь {max(1, count)} вопрос(ов) этого уровня."
    )
    try:
        result = await provider.generate_structured(
            [ChatMessage("system", SYSTEM_PROMPT), ChatMessage("user", prompt)],
            QUESTIONS_SCHEMA,
            schema_name=SCHEMA_NAME,
        )
    except LLMError as exc:
        logger.warning("Генерация вопросов для %s недоступна: %s", topic.key, exc)
        return []
    except Exception:
        logger.exception("Генерация вопросов для %s завершилась ошибкой", topic.key)
        return []

    data = result.data
    if not isinstance(data, dict):
        return []
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list):
        return []
    return [item for item in raw_questions if isinstance(item, dict)]
