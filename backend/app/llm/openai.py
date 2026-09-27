"""LLM-провайдер на базе официального SDK OpenAI (Chat Completions API)."""

import json
from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from app.llm.base import (
    ChatMessage,
    LLMError,
    LLMResponse,
    LLMUsage,
    StructuredResult,
    ToolCall,
    ToolSpec,
)


class OpenAIProvider:
    """Функциональность function calling и структурированного JSON Schema."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate_with_tools(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        """Возвращает ответ LLM с возможными вызовами инструментов."""
        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=_to_openai_messages(messages),
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]
            or None,
        )
        choice = completion.choices[0].message
        tool_calls = tuple(
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=_parse_arguments(call.function.arguments),
            )
            for call in (choice.tool_calls or [])
        )
        return LLMResponse(
            content=choice.content,
            tool_calls=tool_calls,
            usage=_usage(completion.usage),
        )

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: dict[str, Any],
        *,
        schema_name: str = "result",
    ) -> StructuredResult:
        """Возвращает JSON-ответ, соответствующий переданной JSON Schema."""
        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=_to_openai_messages(messages),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        content = completion.choices[0].message.content
        if content is None:
            raise LLMError("OpenAI: пустой ответ при структурированной генерации")
        return StructuredResult(data=json.loads(content), usage=_usage(completion.usage))

    async def close(self) -> None:
        """Закрывает HTTP-клиент SDK."""
        await self._client.close()


def _to_openai_messages(messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    """Конвертирует провайдер-агностичные сообщения в формат Chat Completions API."""
    result: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "tool":
            if message.tool_call_id is None:
                raise LLMError("Сообщение с ролью 'tool' требует tool_call_id")
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": message.content or "",
                }
            )
        elif message.role == "assistant" and message.tool_calls:
            result.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments, ensure_ascii=False),
                            },
                        }
                        for call in message.tool_calls
                    ],
                }
            )
        else:
            result.append({"role": message.role, "content": message.content or ""})
    return result


def _parse_arguments(raw: str | None) -> dict[str, Any]:
    """Парсит JSON-строку аргументов вызова инструмента."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"OpenAI: невалидные аргументы вызова инструмента: {raw!r}") from exc


def _usage(usage: Any) -> LLMUsage | None:
    """Конвертирует usage из ответа SDK в LLMUsage."""
    if usage is None:
        return None
    return LLMUsage(
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
    )
