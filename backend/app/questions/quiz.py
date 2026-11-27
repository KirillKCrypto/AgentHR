"""Ленивая генерация вариантов ответа для вопросов банка."""

import logging
import random
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import ChatMessage, LLMError, LLMProvider
from app.models import Question

logger = logging.getLogger(__name__)

SCHEMA_NAME = "quiz_options"
OPTIONS_PER_QUESTION = 4
MAX_GENERATION_ATTEMPTS = 2
MAX_CORRECT_LENGTH_RATIO = 1.2
MAX_OPTION_LENGTH = 160
MIN_OPTION_LENGTH = 5
BAD_OPTION_MARKERS = (
    "все вышеперечисленное",
    "все перечисленное",
    "ни один из",
    "оба варианта",
    "все варианты",
)

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
    "- Все 4 варианта примерно одинаковой длины: 40–90 символов, разница не больше 20%.\n"
    "- Правильный ответ не должен быть длиннее или подробнее остальных.\n"
    "- Не добавляй в правильный ответ лишние уточнения, которых нет в дистракторах.\n"
    "- Неправильные варианты должны быть такими же конкретными, как правильный.\n"
    "- Не используй слова-подсказки: «всегда», «никогда», «только», «оба варианта».\n"
    "- correct_index — индекс правильного варианта от 0 до 3.\n"
    "- Ставь правильный ответ на разные позиции, не всегда первым.\n"
    "- explanation — 1–2 предложения, почему правильный ответ верен.\n"
    "- Верни ровно по одному элементу на каждый вопрос, number совпадает с номером."
)


class QuizError(ValueError):
    """Не удалось подготовить варианты ответа."""


def options_are_balanced(options: list[str], correct: int) -> bool:
    """Проверяет, что правильный ответ не выделяется длиной или маркером."""
    if len(options) != OPTIONS_PER_QUESTION or len(set(options)) != OPTIONS_PER_QUESTION:
        return False
    if not 0 <= correct < OPTIONS_PER_QUESTION:
        return False
    cleaned = [option.strip() for option in options]
    lengths = [len(option) for option in cleaned]
    if any(length < MIN_OPTION_LENGTH or length > MAX_OPTION_LENGTH for length in lengths):
        return False
    correct_length = lengths[correct]
    distractor_lengths = [
        length for index, length in enumerate(lengths) if index != correct
    ]
    if correct_length > max(distractor_lengths):
        return False
    average_distractor = sum(distractor_lengths) / len(distractor_lengths)
    if correct_length > average_distractor * MAX_CORRECT_LENGTH_RATIO:
        return False
    lowered = [option.lower() for option in cleaned]
    return not any(
        marker in option for option in lowered for marker in BAD_OPTION_MARKERS
    )


def _has_balanced_options(question: Question) -> bool:
    """Есть ли у вопроса готовые и сбалансированные варианты."""
    options = [str(option) for option in question.options or []]
    correct = question.correct_option
    return correct is not None and options_are_balanced(options, correct)


async def ensure_quiz_options(
    session: AsyncSession,
    provider: LLMProvider,
    questions: list[Question],
) -> None:
    """Заполняет или перегенерирует варианты ответа.

    Старые варианты тоже проверяются: LLM часто делала правильный ответ
    самым длинным, поэтому такие вопросы нельзя оставлять в банке.
    """
    pending = [question for question in questions if not _has_balanced_options(question)]
    if not pending:
        return

    for attempt in range(MAX_GENERATION_ATTEMPTS):
        try:
            generated = await _request_options(provider, pending, retry=attempt > 0)
        except LLMError:
            raise
        except Exception as exc:
            raise QuizError("Не удалось подготовить варианты ответов") from exc

        still_pending: list[Question] = []
        for question in pending:
            item = generated.get(id(question))
            if item is None:
                still_pending.append(question)
                continue
            options = [str(option).strip() for option in item.get("options") or []]
            correct = item.get("correct_index")
            if (
                not isinstance(correct, int)
                or len(options) != OPTIONS_PER_QUESTION
                or not 0 <= correct < OPTIONS_PER_QUESTION
            ):
                still_pending.append(question)
                continue
            options, correct = shuffle_options(options, correct)
            if not options_are_balanced(options, correct):
                still_pending.append(question)
                continue
            question.options = options
            question.correct_option = correct
            question.explanation = str(item.get("explanation") or "").strip()[:1000] or None
        pending = still_pending
        if not pending:
            break

    if pending:
        raise QuizError(
            "Не удалось подготовить сбалансированные варианты ответов "
            "с одинаковой длиной"
        )
    await session.flush()


async def _request_options(
    provider: LLMProvider,
    questions: list[Question],
    *,
    retry: bool = False,
) -> dict[int, dict[str, Any]]:
    """Запрашивает варианты и возвращает их по id вопроса."""
    prompt_lines = [
        "Составь варианты ответа для вопросов ниже.",
        "Формат: номер — вопрос; эталонные пункты помогают понять правильный ответ.",
        "",
    ]
    if retry:
        prompt_lines.extend(
            [
                (
                    "Предыдущая попытка была отклонена: правильный ответ оказался "
                    "длиннее остальных или варианты слишком различались по длине."
                ),
                "Сделай все четыре варианта одной длины и одной степени детализации.",
                "",
            ]
        )
    for index, question in enumerate(questions, start=1):
        points = "; ".join(str(item) for item in (question.expected_points or []))
        prompt_lines.append(f"{index}. {question.text}")
        if points:
            prompt_lines.append(f"   Эталонные пункты: {points}")

    result = await provider.generate_structured(
        [ChatMessage("system", SYSTEM_PROMPT), ChatMessage("user", "\n".join(prompt_lines))],
        QUIZ_SCHEMA,
        schema_name=SCHEMA_NAME,
    )
    data = result.data
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise QuizError("LLM вернула некорректный формат вариантов")
    by_number: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        number = item.get("number")
        if isinstance(number, int) and 1 <= number <= len(questions):
            by_number[number] = item
    return {
        id(question): by_number[index]
        for index, question in enumerate(questions, start=1)
        if index in by_number
    }


def shuffle_options(
    options: list[str],
    correct: int,
    *,
    rng: random.Random | None = None,
) -> tuple[list[str], int]:
    """Перемешивает варианты и возвращает новый индекс правильного.

    LLM часто ставит правильный ответ первым, поэтому позицию нельзя оставлять
    на усмотрение модели.
    """
    correct_text = options[correct]
    shuffled = list(options)
    (rng or random.SystemRandom()).shuffle(shuffled)
    return shuffled, shuffled.index(correct_text)


async def shuffle_existing_options(session: AsyncSession) -> int:
    """Перемешивает уже сохранённые варианты, если они были сгенерированы раньше."""
    questions = (
        await session.scalars(
            select(Question).where(Question.correct_option.is_not(None))
        )
    ).all()
    rng = random.SystemRandom()
    for question in questions:
        options = [str(option) for option in question.options or []]
        correct = question.correct_option
        if len(options) != OPTIONS_PER_QUESTION or correct is None:
            continue
        question.options, question.correct_option = shuffle_options(options, correct, rng=rng)
    await session.flush()
    return len(questions)
