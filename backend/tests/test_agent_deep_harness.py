"""Тесты Agent Harness на Deep Agents (мок-LLM): цикл, лимиты, аудит, checkpoint."""

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from app.agent import (
    InMemoryAuditLogger,
    ToolDefinition,
    ToolRegistry,
)
from app.agent.deep_harness import DeepAgentHarness
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


async def test_deep_harness_completes_tool_cycle_and_logs() -> None:
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
    harness = DeepAgentHarness(provider, _echo_registry(), audit_logger=audit)
    session_id = uuid4()

    result = await harness.run(
        [ChatMessage(role="user", content="Сделай эхо")],
        session_id=session_id,
        thread_id="deep-thread-1",
    )

    assert result.status == "completed"
    assert result.final_text == "Готово"
    assert result.steps == 2
    assert result.input_tokens == 17
    assert result.output_tokens == 8
    assert [record.tool_name for record in audit.records] == [None, "echo", None]
    assert [record.step for record in audit.records] == [1, 1, 2]
    assert all(record.session_id == session_id for record in audit.records)
    assert audit.records[1].status == "success"
    assert audit.records[0].input_tokens == 10


async def test_deep_harness_passes_registry_schema_to_model() -> None:
    provider = MockProvider([LLMResponse(content="Ок")])
    harness = DeepAgentHarness(provider, _echo_registry())

    await harness.run([ChatMessage(role="user", content="Схема")], thread_id="deep-thread-2")

    specs = {spec.name: spec for spec in provider.calls[0].tools}
    assert "echo" in specs
    assert specs["echo"].parameters == ECHO_SCHEMA


async def test_deep_harness_stops_at_max_steps() -> None:
    responses = [
        LLMResponse(
            tool_calls=(ToolCall(id=f"call-{index}", name="echo", arguments={"text": str(index)}),)
        )
        for index in range(5)
    ]
    provider = MockProvider(responses)
    harness = DeepAgentHarness(provider, _echo_registry(), max_steps=2)

    result = await harness.run(
        [ChatMessage(role="user", content="Цикл")], thread_id="deep-thread-3"
    )

    assert result.status == "max_steps"
    assert result.steps == 2
    assert len(provider.calls) == 2
    assert result.error is not None
    assert "лимит шагов" in result.error.lower()


async def test_deep_harness_stops_on_token_budget() -> None:
    provider = MockProvider(
        [
            LLMResponse(
                tool_calls=(ToolCall(id="call-1", name="echo", arguments={"text": "x"}),),
                usage=LLMUsage(input_tokens=150, output_tokens=0),
            )
        ]
    )
    harness = DeepAgentHarness(provider, _echo_registry(), token_budget=100)

    result = await harness.run(
        [ChatMessage(role="user", content="Токены")], thread_id="deep-thread-4"
    )

    assert result.status == "token_budget"
    assert len(provider.calls) == 1
    assert result.input_tokens == 150
    assert result.error is not None
    assert "бюджет токенов" in result.error.lower()


async def test_deep_harness_times_out() -> None:
    provider = SlowProvider([LLMResponse(content="не дождёмся")])
    harness = DeepAgentHarness(provider, _echo_registry(), timeout_seconds=0.05)

    result = await harness.run(
        [ChatMessage(role="user", content="Медленно")], thread_id="deep-thread-5"
    )

    assert result.status == "timeout"
    assert result.error is not None


async def test_deep_harness_reports_llm_error() -> None:
    provider = MockProvider()
    harness = DeepAgentHarness(provider, _echo_registry())

    result = await harness.run(
        [ChatMessage(role="user", content="Пустой провайдер")], thread_id="deep-thread-6"
    )

    assert result.status == "llm_error"
    assert result.error is not None
    assert "Ошибка LLM" in result.error


async def test_deep_harness_tool_error_returns_to_model() -> None:
    async def failing(text: str) -> str:
        raise RuntimeError("сломалось")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="fail", description="", parameters=ECHO_SCHEMA, handler=failing)
    )
    audit = InMemoryAuditLogger()
    provider = MockProvider(
        [
            LLMResponse(tool_calls=(ToolCall(id="call-1", name="fail", arguments={"text": "x"}),)),
            LLMResponse(content="Восстановился"),
        ]
    )
    harness = DeepAgentHarness(provider, registry, audit_logger=audit)

    result = await harness.run(
        [ChatMessage(role="user", content="Сбой")], thread_id="deep-thread-7"
    )

    assert result.status == "completed"
    assert result.final_text == "Восстановился"
    tool_records = [record for record in audit.records if record.tool_name == "fail"]
    assert tool_records and tool_records[0].status == "error"
    second_call_messages = provider.calls[1].messages
    assert any(
        message.role == "tool" and "сломалось" in (message.content or "")
        for message in second_call_messages
    )


async def test_deep_harness_rejects_invalid_arguments() -> None:
    provider = MockProvider(
        [
            LLMResponse(tool_calls=(ToolCall(id="call-1", name="echo", arguments={"wrong": 1}),)),
            LLMResponse(content="Понял ошибку"),
        ]
    )
    harness = DeepAgentHarness(provider, _echo_registry())

    result = await harness.run(
        [ChatMessage(role="user", content="Плохие аргументы")], thread_id="deep-thread-8"
    )

    assert result.status == "completed"
    assert any(
        message.role == "tool" and "не соответствуют схеме" in (message.content or "")
        for message in provider.calls[1].messages
    )


async def test_deep_harness_continues_thread_history() -> None:
    provider = MockProvider(
        [LLMResponse(content="Первый ответ"), LLMResponse(content="Второй ответ")]
    )
    harness = DeepAgentHarness(provider, _echo_registry())

    first = await harness.run(
        [ChatMessage(role="user", content="Первый вопрос")], thread_id="deep-thread-9"
    )
    second = await harness.run(
        [ChatMessage(role="user", content="Второй вопрос")], thread_id="deep-thread-9"
    )

    assert first.status == "completed"
    assert second.status == "completed"
    second_call_contents = [message.content for message in provider.calls[1].messages]
    assert "Первый вопрос" in second_call_contents
    assert "Первый ответ" in second_call_contents
    assert "Второй вопрос" in second_call_contents
    assert len(second.messages) == 4
