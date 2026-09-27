"""Тесты Agent Harness на мок-LLM: цикл, лимиты, таймаут, checkpoint, аудит."""

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from app.agent import (
    AgentHarness,
    InMemoryAuditLogger,
    ToolDefinition,
    ToolRegistry,
)
from app.llm import (
    ChatMessage,
    LLMResponse,
    LLMUsage,
    MockProvider,
    ToolCall,
    ToolSpec,
)

ECHO_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}


async def _echo(text: str) -> dict[str, str]:
    return {"echo": text}


def _echo_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Возвращает переданный текст",
            parameters=ECHO_SCHEMA,
            handler=_echo,
        )
    )
    return registry


class SlowProvider(MockProvider):
    """Мок-провайдер с медленным ответом (для проверки таймаута)."""

    async def generate_with_tools(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> LLMResponse:
        await asyncio.sleep(1)
        return await super().generate_with_tools(messages, tools)


async def test_harness_completes_tool_cycle_and_logs() -> None:
    audit = InMemoryAuditLogger()
    provider = MockProvider(
        [
            LLMResponse(
                tool_calls=(ToolCall(id="call-1", name="echo", arguments={"text": "привет"}),),
                usage=LLMUsage(input_tokens=10, output_tokens=5),
            ),
            LLMResponse(content="Готово", usage=LLMUsage(input_tokens=7, output_tokens=3)),
        ]
    )
    harness = AgentHarness(provider, _echo_registry(), audit_logger=audit)
    session_id = uuid4()

    result = await harness.run(
        [ChatMessage(role="user", content="Сделай эхо")],
        session_id=session_id,
        thread_id="thread-1",
    )

    assert result.status == "completed"
    assert result.final_text == "Готово"
    assert result.steps == 2
    assert result.input_tokens == 17
    assert result.output_tokens == 8
    # 2 вызова LLM + 1 инструмент
    assert [record.tool_name for record in audit.records] == [None, "echo", None]
    assert all(record.session_id == session_id for record in audit.records)
    assert audit.records[1].status == "success"
    assert audit.records[0].input_tokens == 10


async def test_harness_stops_at_max_steps() -> None:
    responses = [
        LLMResponse(
            tool_calls=(ToolCall(id=f"call-{index}", name="echo", arguments={"text": str(index)}),)
        )
        for index in range(5)
    ]
    provider = MockProvider(responses)
    harness = AgentHarness(provider, _echo_registry(), max_steps=2)

    result = await harness.run(
        [ChatMessage(role="user", content="Цикл")], thread_id="thread-2"
    )

    assert result.status == "max_steps"
    assert result.steps == 2
    assert len(provider.calls) == 2
    assert result.error is not None
    assert "лимит шагов" in result.error.lower()


async def test_harness_stops_on_token_budget() -> None:
    provider = MockProvider(
        [
            LLMResponse(
                tool_calls=(ToolCall(id="call-1", name="echo", arguments={"text": "x"}),),
                usage=LLMUsage(input_tokens=150, output_tokens=0),
            )
        ]
    )
    harness = AgentHarness(provider, _echo_registry(), token_budget=100)

    result = await harness.run(
        [ChatMessage(role="user", content="Токены")], thread_id="thread-3"
    )

    assert result.status == "token_budget"
    assert len(provider.calls) == 1
    assert result.input_tokens == 150
    assert result.error is not None
    assert "бюджет токенов" in result.error.lower()


async def test_harness_times_out() -> None:
    provider = SlowProvider([LLMResponse(content="не дождёмся")])
    harness = AgentHarness(provider, _echo_registry(), timeout_seconds=0.05)

    result = await harness.run(
        [ChatMessage(role="user", content="Медленно")], thread_id="thread-4"
    )

    assert result.status == "timeout"
    assert result.error is not None


async def test_harness_reports_llm_error() -> None:
    provider = MockProvider()
    harness = AgentHarness(provider, _echo_registry())

    result = await harness.run(
        [ChatMessage(role="user", content="Пустой провайдер")], thread_id="thread-5"
    )

    assert result.status == "llm_error"
    assert result.final_text is not None
    assert "Ошибка LLM" in result.final_text


async def test_harness_tool_error_returns_to_model() -> None:
    async def failing(text: str) -> str:
        raise RuntimeError("сломалось")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="fail", description="", parameters=ECHO_SCHEMA, handler=failing)
    )
    audit = InMemoryAuditLogger()
    provider = MockProvider(
        [
            LLMResponse(
                tool_calls=(ToolCall(id="call-1", name="fail", arguments={"text": "x"}),)
            ),
            LLMResponse(content="Восстановился"),
        ]
    )
    harness = AgentHarness(provider, registry, audit_logger=audit)

    result = await harness.run(
        [ChatMessage(role="user", content="Сбой")], thread_id="thread-6"
    )

    assert result.status == "completed"
    assert result.final_text == "Восстановился"
    assert audit.records[1].tool_name == "fail"
    assert audit.records[1].status == "error"
    second_call_messages = provider.calls[1].messages
    assert any(
        message.role == "tool" and "сломалось" in (message.content or "")
        for message in second_call_messages
    )


async def test_harness_continues_thread_history() -> None:
    provider = MockProvider(
        [LLMResponse(content="Первый ответ"), LLMResponse(content="Второй ответ")]
    )
    harness = AgentHarness(provider, _echo_registry())

    first = await harness.run(
        [ChatMessage(role="user", content="Первый вопрос")], thread_id="thread-7"
    )
    second = await harness.run(
        [ChatMessage(role="user", content="Второй вопрос")], thread_id="thread-7"
    )

    assert first.status == "completed"
    assert second.status == "completed"
    second_call_contents = [message.content for message in provider.calls[1].messages]
    assert "Первый вопрос" in second_call_contents
    assert "Первый ответ" in second_call_contents
    assert "Второй вопрос" in second_call_contents
    # состояние потока накопило историю обоих запусков
    assert len(second.messages) == 4
