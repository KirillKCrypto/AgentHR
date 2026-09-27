"""Слой LLM: провайдер-агностичный интерфейс и реализации."""

from app.llm.base import (
    ChatMessage,
    LLMConfigurationError,
    LLMError,
    LLMProvider,
    LLMResponse,
    LLMUsage,
    StructuredResult,
    ToolCall,
    ToolSpec,
)
from app.llm.factory import create_llm_provider
from app.llm.mock import MockCall, MockProvider
from app.llm.openai import OpenAIProvider

__all__ = [
    "ChatMessage",
    "LLMConfigurationError",
    "LLMError",
    "LLMProvider",
    "LLMResponse",
    "LLMUsage",
    "MockCall",
    "MockProvider",
    "OpenAIProvider",
    "StructuredResult",
    "ToolCall",
    "ToolSpec",
    "create_llm_provider",
]
