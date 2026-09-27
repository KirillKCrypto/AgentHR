"""Настройки приложения (pydantic-settings).

Значения читаются из переменных окружения и файла `backend/.env`
(шаблон — `backend/.env.example`).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки backend-приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AgentHR API"
    environment: str = "local"
    # Локальный дефолт совпадает с infra/.env.example; переопределяется через backend/.env
    database_url: str = "postgresql+asyncpg://agenthr:agenthr@localhost:5433/agenthr"


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный экземпляр настроек (кэшируется)."""
    return Settings()
