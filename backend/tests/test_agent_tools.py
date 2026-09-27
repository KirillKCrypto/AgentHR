"""Тесты реестра инструментов и исполнителя tool-calls (без БД)."""

import asyncio
from typing import Any

import pytest

from app.agent import (
    InMemoryAuditLogger,
    ToolArgumentsError,
    ToolDefinition,
    ToolExecutor,
    ToolNotFoundError,
    ToolRegistry,
)
from app.llm import ToolCall

WEATHER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"],
    "additionalProperties": False,
}


async def _get_weather(city: str) -> dict[str, str]:
    return {"city": city, "weather": "sunny"}


def _registry_with_weather() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="get_weather",
            description="Погода в городе",
            parameters=WEATHER_SCHEMA,
            handler=_get_weather,
        )
    )
    return registry


def test_registry_rejects_duplicate_name() -> None:
    registry = _registry_with_weather()

    with pytest.raises(ValueError):
        registry.register(
            ToolDefinition(
                name="get_weather",
                description="Дубликат",
                parameters=WEATHER_SCHEMA,
                handler=_get_weather,
            )
        )


def test_registry_specs_expose_json_schema() -> None:
    registry = _registry_with_weather()

    specs = registry.specs()

    assert specs[0].name == "get_weather"
    assert specs[0].parameters == WEATHER_SCHEMA


def test_validate_arguments_accepts_valid() -> None:
    registry = _registry_with_weather()

    registry.validate_arguments("get_weather", {"city": "Москва"})


def test_validate_arguments_rejects_invalid() -> None:
    registry = _registry_with_weather()

    with pytest.raises(ToolArgumentsError):
        registry.validate_arguments("get_weather", {"city": 42})


def test_validate_arguments_rejects_unknown_tool() -> None:
    registry = _registry_with_weather()

    with pytest.raises(ToolNotFoundError):
        registry.validate_arguments("unknown", {})


async def test_executor_runs_tool_and_logs_success() -> None:
    audit = InMemoryAuditLogger()
    executor = ToolExecutor(_registry_with_weather(), audit_logger=audit)

    result = await executor.execute(
        ToolCall(id="call-1", name="get_weather", arguments={"city": "Москва"}),
        step=1,
    )

    assert result.status == "success"
    assert "sunny" in result.content
    assert len(audit.records) == 1
    record = audit.records[0]
    assert record.status == "success"
    assert record.tool_name == "get_weather"
    assert record.arguments == {"city": "Москва"}
    assert record.step == 1


async def test_executor_rejects_invalid_arguments_without_calling_handler() -> None:
    called = False

    async def handler(city: str) -> str:
        nonlocal called
        called = True
        return city

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="strict_tool", description="", parameters=WEATHER_SCHEMA, handler=handler)
    )
    audit = InMemoryAuditLogger()
    executor = ToolExecutor(registry, audit_logger=audit)

    result = await executor.execute(
        ToolCall(id="call-1", name="strict_tool", arguments={"nope": 1})
    )

    assert result.status == "error"
    assert not called
    assert audit.records[0].status == "error"


async def test_executor_catches_handler_error() -> None:
    async def failing(city: str) -> str:
        raise RuntimeError("boom")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="failing", description="", parameters=WEATHER_SCHEMA, handler=failing)
    )
    executor = ToolExecutor(registry)

    result = await executor.execute(
        ToolCall(id="call-1", name="failing", arguments={"city": "X"})
    )

    assert result.status == "error"
    assert "boom" in result.content


async def test_executor_applies_timeout() -> None:
    async def slow(city: str) -> str:
        await asyncio.sleep(1)
        return city

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="slow", description="", parameters=WEATHER_SCHEMA, handler=slow)
    )
    executor = ToolExecutor(registry, timeout_seconds=0.05)

    result = await executor.execute(ToolCall(id="call-1", name="slow", arguments={"city": "X"}))

    assert result.status == "error"
    assert "Таймаут" in result.content
