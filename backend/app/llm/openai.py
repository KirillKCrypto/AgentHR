"""LLM-провайдер на базе официального SDK OpenAI (Chat Completions API)."""

import json
import logging
import re
from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI, OpenAIError

from app.llm.base import (
    ChatMessage,
    LLMError,
    LLMResponse,
    LLMUsage,
    StructuredResult,
    ToolCall,
    ToolSpec,
)

logger = logging.getLogger(__name__)

# Промпт резервного режима: некоторые OpenAI-совместимые шлюзы не поддерживают
# `response_format=json_schema`, но понимают схему в тексте запроса.
_SCHEMA_INSTRUCTION = (
    "Верни только JSON-объект, соответствующий этой JSON Schema:\n{schema}\n"
    "Без markdown, без пояснений и без текста до или после JSON."
)


class OpenAIProvider:
    """Функциональность function calling и структурированного JSON Schema."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 0,
    ) -> None:
        """Создаёт клиент; таймаут ограничивает ожидание ответа модели.

        Ретраи по умолчанию выключены: шлюзы бесплатных моделей отвечают
        неравномерно, и лучше вернуть понятную ошибку, чем держать запрос
        пользователя минутами.
        """
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._model = model

    async def generate_with_tools(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        """Возвращает ответ LLM с возможными вызовами инструментов."""
        try:
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
        except OpenAIError as exc:
            raise LLMError(f"OpenAI: запрос не выполнен — {exc}") from exc

        choice = completion.choices[0].message
        try:
            tool_calls = tuple(
                ToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=_parse_arguments(call.function.arguments),
                )
                for call in (choice.tool_calls or [])
            )
        except (AttributeError, IndexError) as exc:
            raise LLMError("OpenAI: неожиданная структура вызова инструмента") from exc

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
        """Возвращает JSON-ответ, соответствующий переданной JSON Schema.

        Сначала используется штатный `response_format=json_schema`. Если шлюз
        его не поддерживает или запрос не прошёл (бесплатные прокси отвечают
        неравномерно), запрос один раз повторяется с описанием схемы в промпте —
        так пайплайн работает и на шлюзах, которые умеют только обычный чат.
        """
        try:
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
        except OpenAIError as exc:
            logger.warning(
                "Запрос со строгой JSON Schema не прошёл (%s), повторяю без неё", exc
            )
            completion = await self._generate_prompt_json(messages, schema)

        content = completion.choices[0].message.content
        if content is None:
            raise LLMError("OpenAI: пустой ответ при структурированной генерации")
        return StructuredResult(data=_parse_json_object(content), usage=_usage(completion.usage))

    async def _generate_prompt_json(
        self,
        messages: Sequence[ChatMessage],
        schema: dict[str, Any],
    ) -> Any:
        """Резервный запрос: схема описывается в системном сообщении."""
        instruction = ChatMessage(
            role="system",
            content=_SCHEMA_INSTRUCTION.format(
                schema=json.dumps(schema, ensure_ascii=False)
            ),
        )
        try:
            return await self._client.chat.completions.create(
                model=self._model,
                messages=_to_openai_messages([instruction, *messages]),
            )
        except OpenAIError as exc:
            raise LLMError(f"OpenAI: запрос не выполнен — {exc}") from exc

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


def _parse_json_object(content: str) -> dict[str, Any]:
    """Разбирает JSON-объект из ответа модели, снимая markdown-обёртку."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[A-Za-z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError(f"OpenAI: ответ не является JSON: {content[:200]!r}") from None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"OpenAI: ответ не является JSON: {content[:200]!r}") from exc

    if not isinstance(data, dict):
        raise LLMError("OpenAI: структурированный ответ должен быть JSON-объектом")
    return data


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
