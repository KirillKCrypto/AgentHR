"""Тесты слоя LLM: MockProvider без сети и опциональная живая проверка внешнего API."""

import os
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APIStatusError

from app.core.config import Settings, get_settings
from app.llm import (
    ChatMessage,
    LLMConfigurationError,
    LLMError,
    LLMResponse,
    LLMUsage,
    MockProvider,
    OpenAIProvider,
    ToolCall,
    ToolSpec,
    create_llm_provider,
)

SIMPLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"answer": {"type": "integer"}},
    "required": ["answer"],
    "additionalProperties": False,
}

USER_MESSAGE = [ChatMessage(role="user", content="Сколько будет 2+2?")]


async def test_mock_returns_scripted_tool_calls() -> None:
    expected = LLMResponse(
        tool_calls=(
            ToolCall(id="call-1", name="get_weather", arguments={"city": "Москва"}),
        ),
        usage=LLMUsage(input_tokens=10, output_tokens=5),
    )
    provider = MockProvider([expected])
    tool_spec = ToolSpec(name="get_weather", description="Погода", parameters={"type": "object"})

    result = await provider.generate_with_tools(USER_MESSAGE, [tool_spec])

    assert result == expected
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call.operation == "generate_with_tools"
    assert call.tools[0].name == "get_weather"
    assert call.messages[0].content == "Сколько будет 2+2?"


async def test_mock_returns_structured_result() -> None:
    provider = MockProvider([LLMResponse(content='{"answer": 42}')])

    result = await provider.generate_structured(USER_MESSAGE, SIMPLE_SCHEMA, schema_name="answer")

    assert result.data == {"answer": 42}
    assert provider.calls[0].operation == "generate_structured"
    assert provider.calls[0].schema_name == "answer"


async def test_mock_raises_when_queue_is_empty() -> None:
    provider = MockProvider()

    with pytest.raises(LLMError):
        await provider.generate_with_tools(USER_MESSAGE, [])


def test_factory_defaults_to_mock() -> None:
    provider = create_llm_provider(Settings(llm_provider="mock"))

    assert isinstance(provider, MockProvider)


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(LLMConfigurationError):
        create_llm_provider(Settings(llm_provider="unknown"))


def test_factory_openai_requires_key_and_model() -> None:
    with pytest.raises(LLMConfigurationError):
        create_llm_provider(
            Settings(llm_provider="openai", openai_api_key=None, openai_model=None)
        )


async def test_factory_builds_openai_provider_with_credentials() -> None:
    provider = create_llm_provider(
        Settings(llm_provider="openai", openai_api_key="test-key", openai_model="test-model")
    )
    try:
        assert isinstance(provider, OpenAIProvider)
    finally:
        await provider.close()


async def test_factory_passes_structured_mode() -> None:
    provider = create_llm_provider(
        Settings(
            llm_provider="openai",
            openai_api_key="test-key",
            openai_model="test-model",
            llm_structured_mode="json_object",
        )
    )
    try:
        assert isinstance(provider, OpenAIProvider)
        assert provider._structured_mode == "json_object"
    finally:
        await provider.close()


def test_openai_provider_rejects_unknown_structured_mode() -> None:
    with pytest.raises(LLMConfigurationError):
        OpenAIProvider(
            api_key="test-key",
            model="test-model",
            structured_mode="unknown",  # type: ignore[arg-type]
        )


async def test_openai_provider_wraps_transport_errors() -> None:
    """Сбой сети превращается в доменную ошибку LLM, а не в 500."""
    provider = OpenAIProvider(api_key="test-key", model="test-model")
    provider._client.chat.completions.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=APIConnectionError(
            request=httpx.Request("POST", "https://example.com/v1/chat/completions")
        )
    )
    try:
        with pytest.raises(LLMError, match="запрос не выполнен"):
            await provider.generate_structured(USER_MESSAGE, SIMPLE_SCHEMA)
    finally:
        await provider.close()


async def test_openai_provider_rejects_non_json_answer() -> None:
    """Не-JSON ответ модели — понятная ошибка провайдера."""
    provider = OpenAIProvider(api_key="test-key", model="test-model")
    fake_completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="не json"))],
        usage=None,
    )
    provider._client.chat.completions.create = AsyncMock(  # type: ignore[method-assign]
        return_value=fake_completion
    )
    try:
        with pytest.raises(LLMError, match="не является JSON"):
            await provider.generate_structured(USER_MESSAGE, SIMPLE_SCHEMA)
    finally:
        await provider.close()


async def test_openai_provider_falls_back_when_json_schema_unsupported() -> None:
    """Если шлюз не умеет json_schema, схема уходит в промпт, ответ разбирается."""
    provider = OpenAIProvider(api_key="test-key", model="test-model")
    status_error = APIStatusError(
        "unsupported",
        response=httpx.Response(
            410, request=httpx.Request("POST", "https://example.com/v1/chat/completions")
        ),
        body=None,
    )
    fake_completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='```json\n{"answer": 4}\n```')
            )
        ],
        usage=None,
    )
    create = AsyncMock(side_effect=[status_error, fake_completion])
    provider._client.chat.completions.create = create  # type: ignore[method-assign]
    try:
        result = await provider.generate_structured(USER_MESSAGE, SIMPLE_SCHEMA)

        assert result.data == {"answer": 4}
        assert create.await_count == 2
        second_call = create.await_args_list[1].kwargs
        assert "response_format" not in second_call
        assert "JSON Schema" in second_call["messages"][0]["content"]
    finally:
        await provider.close()


async def test_openai_provider_json_object_mode_skips_json_schema() -> None:
    """В режиме json_object схема идёт в промпт, а json_schema не запрашивается."""
    provider = OpenAIProvider(
        api_key="test-key", model="test-model", structured_mode="json_object"
    )
    fake_completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"answer": 4}'))],
        usage=None,
    )
    create = AsyncMock(return_value=fake_completion)
    provider._client.chat.completions.create = create  # type: ignore[method-assign]
    try:
        result = await provider.generate_structured(USER_MESSAGE, SIMPLE_SCHEMA)

        assert result.data == {"answer": 4}
        assert create.await_count == 1
        request = create.await_args.kwargs
        assert request["response_format"] == {"type": "json_object"}
        assert "JSON Schema" in request["messages"][0]["content"]
    finally:
        await provider.close()


async def test_openai_provider_prompt_mode_omits_response_format() -> None:
    """В режиме prompt API не получает response_format вовсе."""
    provider = OpenAIProvider(api_key="test-key", model="test-model", structured_mode="prompt")
    fake_completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"answer": 4}'))],
        usage=None,
    )
    create = AsyncMock(return_value=fake_completion)
    provider._client.chat.completions.create = create  # type: ignore[method-assign]
    try:
        result = await provider.generate_structured(USER_MESSAGE, SIMPLE_SCHEMA)

        assert result.data == {"answer": 4}
        assert "response_format" not in create.await_args.kwargs
    finally:
        await provider.close()


_live_settings = get_settings()
_LIVE_ENABLED = os.environ.get("RUN_LIVE_LLM_TESTS") == "1"


@pytest.mark.skipif(
    not _LIVE_ENABLED,
    reason="Живой тест LLM выключен: задайте RUN_LIVE_LLM_TESTS=1",
)
@pytest.mark.skipif(
    not (_live_settings.openai_api_key and _live_settings.openai_model),
    reason="OPENAI_API_KEY и OPENAI_MODEL не заданы — живой тест пропущен",
)
async def test_openai_structured_live() -> None:
    """Живой вызов OpenAI-совместимого API (только по явному флагу)."""
    assert _live_settings.openai_api_key is not None
    assert _live_settings.openai_model is not None
    provider = OpenAIProvider(
        api_key=_live_settings.openai_api_key,
        model=_live_settings.openai_model,
        base_url=_live_settings.openai_base_url,
        structured_mode=_live_settings.llm_structured_mode,
    )
    try:
        result = await provider.generate_structured(
            [
                ChatMessage(
                    role="user",
                    content="Ответь JSON по схеме: сколько будет 2+2? Поле answer — целое число.",
                )
            ],
            SIMPLE_SCHEMA,
        )
        assert result.data["answer"] == 4
    finally:
        await provider.close()
