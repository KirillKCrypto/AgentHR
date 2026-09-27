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
    # JWT: локальный dev-дефолт; в продакшене обязательно переопределить через .env
    jwt_secret_key: str = "dev-insecure-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    # LLM: по умолчанию mock (без сети); openai требует ключ и модель
    llm_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str | None = None
    # CORS: браузерные источники, которым разрешены запросы (frontend dev-сервер)
    cors_origins: list[str] = ["http://localhost:5173"]
    # Agent Harness: лимиты цикла
    agent_max_steps: int = 10
    agent_token_budget: int = 50000
    agent_timeout_seconds: float = 120
    agent_tool_timeout_seconds: float = 30


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный экземпляр настроек (кэшируется)."""
    return Settings()
