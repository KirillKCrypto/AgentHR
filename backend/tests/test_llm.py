"""Тесты слоя LLM: MockProvider без сети и опциональная живая проверка OpenAI."""

from typing import Any

import pytest

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


_live_settings = get_settings()


@pytest.mark.skipif(
    not (_live_settings.openai_api_key and _live_settings.openai_model),
    reason="OPENAI_API_KEY и OPENAI_MODEL не заданы — живой тест пропущен",
)
async def test_openai_structured_live() -> None:
    """Живой вызов OpenAI (выполняется только при наличии ключа и модели в .env)."""
    assert _live_settings.openai_api_key is not None
    assert _live_settings.openai_model is not None
    provider = OpenAIProvider(
        api_key=_live_settings.openai_api_key,
        model=_live_settings.openai_model,
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
