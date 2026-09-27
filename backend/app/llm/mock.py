"""Детерминированный мок-провайдер для тестов (без сетевых вызовов)."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.llm.base import (
    ChatMessage,
    LLMError,
    LLMResponse,
    StructuredResult,
    ToolSpec,
)


@dataclass(frozen=True)
class MockCall:
    """Записанный вызов мок-провайдера (для проверок в тестах)."""

    operation: str
    messages: tuple[ChatMessage, ...]
    tools: tuple[ToolSpec, ...] = ()
    schema: dict[str, Any] | None = None
    schema_name: str | None = None


class MockProvider:
    """Отдаёт заранее заданные ответы по порядку и записывает вызовы.

    Для `generate_structured` поле `content` ответа должно быть JSON-строкой.
    """

    def __init__(self, responses: Sequence[LLMResponse] | None = None) -> None:
        self._responses = list(responses or [])
        self.calls: list[MockCall] = []

    def _next(self) -> LLMResponse:
        if not self._responses:
            raise LLMError("MockProvider: очередь ответов пуста")
        return self._responses.pop(0)

    async def generate_with_tools(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        """Возвращает следующий запрограммированный ответ."""
        self.calls.append(MockCall("generate_with_tools", tuple(messages), tools=tuple(tools)))
        return self._next()

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: dict[str, Any],
        *,
        schema_name: str = "result",
    ) -> StructuredResult:
        """Возвращает распарсенный JSON из следующего запрограммированного ответа."""
        self.calls.append(
            MockCall(
                "generate_structured",
                tuple(messages),
                schema=schema,
                schema_name=schema_name,
            )
        )
        response = self._next()
        if response.content is None:
            raise LLMError("MockProvider: для структурированного ответа нужен content")
        return StructuredResult(data=json.loads(response.content), usage=response.usage)

    async def close(self) -> None:
        """Ничего не делает: у мока нет ресурсов."""
