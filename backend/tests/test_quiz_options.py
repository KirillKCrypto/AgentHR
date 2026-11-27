"""Качество вариантов ответа: правильный ответ не должен быть длиннее."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.llm.base import StructuredResult
from app.questions.quiz import QuizError, ensure_quiz_options, options_are_balanced


class SequenceProvider:
    """Провайдер, отдающий заранее заданные ответы по очереди."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    async def generate_structured(
        self,
        messages,
        schema,
        *,
        schema_name: str = "result",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> StructuredResult:
        self.calls.append(schema_name)
        return StructuredResult(data=self.responses.pop(0))


class FakeSession:
    """Заглушка сессии: flush не требуется."""

    async def flush(self) -> None:
        return None


def _question() -> Any:
    return SimpleNamespace(
        text="Как работает Python?",
        expected_points=["интерпретатор"],
        options=[],
        correct_option=None,
        explanation=None,
    )


def _item(options: list[str], correct: int) -> dict[str, Any]:
    return {
        "number": 1,
        "options": options,
        "correct_index": correct,
        "explanation": "Пояснение",
    }


def test_options_are_balanced_rejects_long_correct_answer() -> None:
    """Длинный правильный ответ — это подсказка, а не проверка знаний."""
    options = [
        "Короткий",
        "Другой",
        "Третий",
        "Очень длинный правильный ответ с лишними подробностями",
    ]
    assert options_are_balanced(options, 3) is False


def test_options_are_balanced_accepts_equal_length() -> None:
    """Варианты одной длины проходят проверку."""
    options = [
        "Использует интерпретатор",
        "Компилирует в байткод",
        "Работает через JIT",
        "Выполняет виртуальная машина",
    ]
    assert options_are_balanced(options, 0) is True


async def test_ensure_quiz_options_retries_biased_generation() -> None:
    """Первый ответ с длинным правильным перегенерируется."""
    provider = SequenceProvider(
        [
            {
                "items": [
                    _item(
                        [
                            "Короткий",
                            "Другой",
                            "Третий",
                            "Очень длинный правильный ответ с подробностями",
                        ],
                        3,
                    )
                ]
            },
            {
                "items": [
                    _item(
                        [
                            "Короткий ответ",
                            "Другой ответ",
                            "Третий ответ",
                            "Четвёртый ответ",
                        ],
                        2,
                    )
                ]
            },
        ]
    )
    question = _question()
    await ensure_quiz_options(FakeSession(), provider, [question])

    assert provider.calls == ["quiz_options", "quiz_options"]
    assert question.correct_option is not None
    assert question.options[question.correct_option] == "Третий ответ"
    assert options_are_balanced(question.options, question.correct_option)


async def test_ensure_quiz_options_fails_after_two_biased_attempts() -> None:
    """Два плохих ответа подряд не попадают в тест."""
    biased = {
        "items": [
            _item(
                [
                    "Короткий",
                    "Другой",
                    "Третий",
                    "Очень длинный правильный ответ с подробностями",
                ],
                3,
            )
        ]
    }
    provider = SequenceProvider([biased, biased])
    with pytest.raises(QuizError):
        await ensure_quiz_options(FakeSession(), provider, [_question()])
    assert provider.calls == ["quiz_options", "quiz_options"]
