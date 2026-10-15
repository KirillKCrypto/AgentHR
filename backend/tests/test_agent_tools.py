"""Тесты реестра инструментов и адаптера инструментов для LangChain (без БД)."""

import asyncio
import json
from typing import Any

import pytest

from app.agent import (
    ToolArgumentsError,
    ToolDefinition,
    ToolNotFoundError,
    ToolRegistry,
)
from app.agent.langchain_tools import RegistryTool, build_registry_tools

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


def test_langchain_tool_exposes_registry_schema() -> None:
    tools = build_registry_tools(_registry_with_weather(), timeout_seconds=5.0)

    assert len(tools) == 1
    assert isinstance(tools[0], RegistryTool)
    assert tools[0].name == "get_weather"
    assert tools[0].tool_call_schema == WEATHER_SCHEMA


async def test_langchain_tool_runs_handler() -> None:
    tool = build_registry_tools(_registry_with_weather(), timeout_seconds=5.0)[0]

    content = await tool.ainvoke({"city": "Москва"})

    assert json.loads(content) == {"city": "Москва", "weather": "sunny"}


async def test_langchain_tool_rejects_invalid_arguments_without_calling_handler() -> None:
    called = False

    async def handler(city: str) -> str:
        nonlocal called
        called = True
        return city

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="strict_tool", description="", parameters=WEATHER_SCHEMA, handler=handler
        )
    )
    tool = build_registry_tools(registry, timeout_seconds=5.0)[0]

    with pytest.raises(ToolArgumentsError):
        await tool.ainvoke({"nope": 1})
    assert not called


async def test_langchain_tool_propagates_handler_error() -> None:
    async def failing(city: str) -> str:
        raise RuntimeError("boom")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="failing", description="", parameters=WEATHER_SCHEMA, handler=failing)
    )
    tool = build_registry_tools(registry, timeout_seconds=5.0)[0]

    with pytest.raises(RuntimeError, match="boom"):
        await tool.ainvoke({"city": "X"})


async def test_langchain_tool_applies_timeout() -> None:
    async def slow(city: str) -> str:
        await asyncio.sleep(1)
        return city

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="slow", description="", parameters=WEATHER_SCHEMA, handler=slow)
    )
    tool = build_registry_tools(registry, timeout_seconds=0.05)[0]

    with pytest.raises(TimeoutError, match="Таймаут"):
        await tool.ainvoke({"city": "X"})
