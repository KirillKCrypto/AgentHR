"""Второй проход оценки запускается только при неуверенности."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

from app.llm.base import (
    ChatMessage,
    LLMError,
    LLMResponse,
    StructuredResult,
    ToolSpec,
)
from app.models import InterviewTurn
from app.services.interview import _evaluate_answer

BASE_DATA: dict[str, Any] = {
    "correctness": 48,
    "coverage": 20,
    "depth": 8,
    "relevance": "on_topic",
    "point_assessments": [],
    "critical_errors": [],
    "covered_points": ["суть"],
    "missed_points": [],
    "feedback_brief": "Ответ по существу.",
}


class CountingProvider:
    """Провайдер, считающий структурированные вызовы."""

    def __init__(self, confidence: float) -> None:
        self.calls = 0
        self.confidence = confidence

    async def generate_with_tools(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> LLMResponse:
        """Не используется."""
        raise NotImplementedError

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: dict[str, Any],
        *,
        schema_name: str = "result",
        max_tokens: int | None = None,
    ) -> StructuredResult:
        """Возвращает один и тот же разбор."""
        self.calls += 1
        return StructuredResult(
            data={**BASE_DATA, "confidence": self.confidence}
        )

    async def generate_stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        """Не используется."""
        yield ""

    async def close(self) -> None:
        """Ресурсов нет."""


def _turn() -> InterviewTurn:
    """Ход интервью без сохранения в БД."""
    return InterviewTurn(
        question_text="Что такое декоратор?",
        difficulty=3,
        expected_points=["суть"],
    )


async def test_confident_evaluation_uses_one_call() -> None:
    """Уверенная оценка не делает второй запрос."""
    provider = CountingProvider(confidence=0.9)

    result = await _evaluate_answer(provider, _turn(), "Ответ по существу.")

    assert provider.calls == 1
    assert result["breakdown"]["evaluation_ms"] >= 0


async def test_uncertain_evaluation_is_repeated() -> None:
    """Неуверенная оценка перепроверяется вторым вызовом."""
    provider = CountingProvider(confidence=0.4)

    await _evaluate_answer(provider, _turn(), "Ответ по существу.")

    assert provider.calls == 2


class EmptyOnceProvider(CountingProvider):
    """Первый ответ пустой, второй — корректный."""

    def __init__(self) -> None:
        super().__init__(confidence=0.9)

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: dict[str, Any],
        *,
        schema_name: str = "result",
        max_tokens: int | None = None,
    ) -> StructuredResult:
        """Имитирует пустой ответ модели."""
        self.calls += 1
        if self.calls == 1:
            raise LLMError("LLM: ответ не является JSON: ''")
        return StructuredResult(data={**BASE_DATA, "confidence": self.confidence})


async def test_empty_response_is_retried() -> None:
    """Пустой ответ не превращается в 502 с первого раза."""
    provider = EmptyOnceProvider()

    result = await _evaluate_answer(provider, _turn(), "Ответ по существу.")

    assert provider.calls == 2
    assert result["score"] > 0

