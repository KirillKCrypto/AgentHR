"""Адаптер LLM-слоя AgentHR к интерфейсу LangChain (`BaseChatModel`).

Нужен, чтобы Deep Agents мог использовать наш провайдер-агностичный слой
`app/llm` — включая `MockProvider` в тестах (без сети) и `OpenAIProvider`.
"""

from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import ConfigDict

from app.llm.base import ChatMessage, LLMProvider, LLMResponse, ToolCall, ToolSpec


def message_text(content: Any) -> str:
    """Приводит содержимое сообщения LangChain к строке."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return "" if content is None else str(content)


def to_chat_messages(messages: Sequence[BaseMessage]) -> list[ChatMessage]:
    """Конвертирует сообщения LangChain в сообщения слоя AgentHR."""
    converted: list[ChatMessage] = []
    for message in messages:
        text = message_text(message.content)
        if isinstance(message, SystemMessage):
            converted.append(ChatMessage(role="system", content=text))
        elif isinstance(message, ToolMessage):
            converted.append(
                ChatMessage(
                    role="tool",
                    content=text,
                    tool_call_id=str(message.tool_call_id),
                )
            )
        elif isinstance(message, AIMessage):
            calls = tuple(
                ToolCall(
                    id=str(call.get("id") or ""),
                    name=str(call["name"]),
                    arguments=dict(call.get("args") or {}),
                )
                for call in (message.tool_calls or [])
            )
            converted.append(ChatMessage(role="assistant", content=text or None, tool_calls=calls))
        elif isinstance(message, HumanMessage):
            converted.append(ChatMessage(role="user", content=text))
        else:
            converted.append(ChatMessage(role="user", content=text))
    return converted


def to_ai_message(response: LLMResponse) -> AIMessage:
    """Конвертирует ответ нашего провайдера в `AIMessage`."""
    tool_calls = [
        {"name": call.name, "args": call.arguments, "id": call.id, "type": "tool_call"}
        for call in response.tool_calls
    ]
    usage_metadata: dict[str, int] | None = None
    if response.usage is not None:
        input_tokens = response.usage.input_tokens or 0
        output_tokens = response.usage.output_tokens or 0
        usage_metadata = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
    return AIMessage(
        content=response.content or "",
        tool_calls=tool_calls,
        usage_metadata=usage_metadata,
    )


def _tool_schema(tool: BaseTool) -> dict[str, Any]:
    """Возвращает JSON Schema инструмента LangChain."""
    schema = tool.tool_call_schema
    if isinstance(schema, dict):
        return schema
    return schema.model_json_schema()


def tool_spec_from(value: BaseTool | dict[str, Any] | Any) -> ToolSpec:
    """Приводит инструмент LangChain (или dict-описание) к `ToolSpec`."""
    if isinstance(value, BaseTool):
        return ToolSpec(
            name=value.name,
            description=value.description or "",
            parameters=_tool_schema(value),
        )
    if isinstance(value, dict):
        parameters = value.get("parameters") or value.get("input_schema") or {}
        return ToolSpec(
            name=str(value.get("name") or ""),
            description=str(value.get("description") or ""),
            parameters=dict(parameters),
        )
    # Инструмент-функция: LangChain умеет выдать его OpenAI-описание
    from langchain_core.utils.function_calling import convert_to_openai_tool

    spec = convert_to_openai_tool(value)
    function = spec.get("function", {})
    return ToolSpec(
        name=str(function.get("name") or ""),
        description=str(function.get("description") or ""),
        parameters=dict(function.get("parameters") or {}),
    )


class ProviderChatModel(BaseChatModel):
    """Мост «наш `LLMProvider` → LangChain-модель»."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: Any
    """Провайдер LLM AgentHR (`app.llm.base.LLMProvider`)."""

    tool_specs: tuple[ToolSpec, ...] = ()
    """Описания инструментов, привязанных через `bind_tools`."""

    @property
    def _llm_type(self) -> str:
        """Идентификатор типа модели для LangChain."""
        return "agenthr-provider"

    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, Any] | Any],
        **kwargs: Any,
    ) -> Any:
        """Привязывает инструменты, переводя их в описания нашего слоя LLM."""
        specs = tuple(tool_spec_from(tool) for tool in tools)
        return self.bind(tool_specs=specs, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Вызывает провайдер AgentHR и возвращает ответ как `AIMessage`."""
        specs: Sequence[ToolSpec] = kwargs.get("tool_specs") or self.tool_specs
        response = await self._provider().generate_with_tools(
            to_chat_messages(messages), list(specs)
        )
        return ChatResult(generations=[ChatGeneration(message=to_ai_message(response))])

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Синхронная генерация не поддерживается: слой AgentHR только async."""
        message = (
            "ProviderChatModel поддерживает только асинхронные вызовы (используйте ainvoke/astream)"
        )
        raise NotImplementedError(message)

    def _provider(self) -> LLMProvider:
        """Возвращает провайдер с проверкой контракта."""
        provider = self.provider
        if provider is None:  # pragma: no cover — защита от неверной сборки
            message = "ProviderChatModel создан без провайдера LLM"
            raise ValueError(message)
        return provider
