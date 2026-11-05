"""Ленивая генерация вариантов ответа для вопросов банка."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import ChatMessage, LLMError, LLMProvider
from app.models import Question

logger = logging.getLogger(__name__)

SCHEMA_NAME = "quiz_options"
OPTIONS_PER_QUESTION = 4

QUIZ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["number", "options", "correct_index", "explanation"],
                "properties": {
                    "number": {
                        "type": "integer",
                        "description": "Номер вопроса из промпта, начиная с 1",
                    },
                    "options": {
                        "type": "array",
                        "minItems": OPTIONS_PER_QUESTION,
                        "maxItems": OPTIONS_PER_QUESTION,
                        "items": {"type": "string"},
                    },
                    "correct_index": {"type": "integer", "minimum": 0, "maximum": 3},
                    "explanation": {"type": "string"},
                },
            },
        }
    },
}

SYSTEM_PROMPT = (
    "Ты составляешь тест с одним правильным ответом по техническим вопросам.\n"
    "Для каждого вопроса придумай 4 коротких варианта ответа: один правильный и три "
    "правдоподобных неправильных.\n"
    "Правила:\n"
    "- Варианты на русском, без «все вышеперечисленное» и «ни один».\n"
    "- Неправильные варианты должны быть похожи по стилю, но ошибочны по сути.\n"
    "- correct_index — индекс правильного варианта от 0 до 3.\n"
    "- explanation — 1–2 предложения, почему правильный ответ верен.\n"
    "- Верни ровно по одному элементу на каждый вопрос, number совпадает с номером."
)


class QuizError(ValueError):
    """Не удалось подготовить варианты ответа."""


async def ensure_quiz_options(
    session: AsyncSession,
    provider: LLMProvider,
    questions: list[Question],
) -> None:
    """Заполняет options/correct_option/explanation для выбранных вопросов."""
    missing = [question for question in questions if not question.options or question.correct_option is None]
    if not missing:
        return

    prompt_lines = [
        "Составь варианты ответа для вопросов ниже.",
        "Формат: номер — вопрос; эталонные пункты помогают понять правильный ответ.",
        "",
    ]
    for index, question in enumerate(missing, start=1):
        points = "; ".join(str(item) for item in (question.expected_points or []))
        prompt_lines.append(f"{index}. {question.text}")
        if points:
            prompt_lines.append(f"   Эталонные пункты: {points}")

    try:
        result = await provider.generate_structured(
            [ChatMessage("system", SYSTEM_PROMPT), ChatMessage("user", "\n".join(prompt_lines))],
            QUIZ_SCHEMA,
            schema_name=SCHEMA_NAME,
        )
    except LLMError:
        raise
    except Exception as exc:
        raise QuizError("Не удалось подготовить варианты ответов") from exc

    data = result.data
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise QuizError("LLM вернула некорректный формат вариантов")

    by_number: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        number = item.get("number")
        if isinstance(number, int) and 1 <= number <= len(missing):
            by_number[number] = item

    if len(by_number) != len(missing):
        raise QuizError("LLM вернула не все вопросы с вариантами")

    for index, question in enumerate(missing, start=1):
        item = by_number[index]
        options = [str(option).strip() for option in item.get("options") or []]
        correct = item.get("correct_index")
        if len(options) != OPTIONS_PER_QUESTION or not isinstance(correct, int):
            raise QuizError("LLM вернула некорректные варианты ответа")
        if not 0 <= correct < OPTIONS_PER_QUESTION or len(set(options)) != OPTIONS_PER_QUESTION:
            raise QuizError("LLM вернула некорректный правильный ответ")
        question.options = options
        question.correct_option = correct
        question.explanation = str(item.get("explanation") or "").strip()[:1000] or None

    await session.flush()
