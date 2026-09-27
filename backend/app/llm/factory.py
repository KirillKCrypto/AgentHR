"""Фабрика LLM-провайдера по настройкам приложения."""

from app.core.config import Settings, get_settings
from app.llm.base import LLMConfigurationError, LLMProvider
from app.llm.mock import MockProvider
from app.llm.openai import OpenAIProvider


def create_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Создаёт провайдера LLM по настройкам (по умолчанию — mock)."""
    current = settings or get_settings()

    if current.llm_provider == "mock":
        return MockProvider()
    if current.llm_provider == "openai":
        if not current.openai_api_key or not current.openai_model:
            raise LLMConfigurationError(
                "Для LLM_PROVIDER=openai задайте OPENAI_API_KEY и OPENAI_MODEL"
            )
        return OpenAIProvider(api_key=current.openai_api_key, model=current.openai_model)

    raise LLMConfigurationError(f"Неизвестный LLM_PROVIDER: {current.llm_provider!r}")
