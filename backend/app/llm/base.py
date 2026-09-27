"""Базовые типы и интерфейс LLM-провайдера (провайдер-агностичный слой)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


class LLMError(Exception):
    """Общая ошибка слоя LLM."""


class LLMConfigurationError(LLMError):
    """Некорректная конфигурация LLM-провайдера."""


@dataclass(frozen=True)
class ToolSpec:
    """Описание инструмента для LLM (JSON Schema параметров)."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """Запрос LLM на вызов инструмента."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatMessage:
    """Сообщение диалога.

    Для `role="assistant"` может содержать `tool_calls`, для `role="tool"` —
    `tool_call_id` и результат в `content`.
    """

    role: Role
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class LLMUsage:
    """Расход токенов (используется в audit-логе)."""

    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Ответ LLM: текст и/или вызовы инструментов."""

    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    usage: LLMUsage | None = None


@dataclass(frozen=True)
class StructuredResult:
    """Результат структурированной генерации по JSON Schema."""

    data: dict[str, Any]
    usage: LLMUsage | None = None


class LLMProvider(Protocol):
    """Интерфейс провайдера LLM."""

    async def generate_with_tools(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        """Возвращает ответ LLM с возможными вызовами инструментов."""
        ...

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: dict[str, Any],
        *,
        schema_name: str = "result",
    ) -> StructuredResult:
        """Возвращает JSON-ответ, соответствующий переданной JSON Schema."""
        ...

    async def close(self) -> None:
        """Освобождает ресурсы провайдера."""
        ...
