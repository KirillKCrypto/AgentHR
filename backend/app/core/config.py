"""Настройки приложения (pydantic-settings).

Значения читаются из переменных окружения и файла `backend/.env`
(шаблон — `backend/.env.example`).
"""

from functools import lru_cache
from typing import Literal

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
    openai_base_url: str | None = None  # для OpenAI-совместимых API (DeepSeek и другие)
    # Режим структурированного вывода:
    #   json_schema — штатный response_format=json_schema с откатом в промпт;
    #   json_object — response_format=json_object + схема в промпте (DeepSeek);
    #   prompt      — только схема в промпте, без response_format.
    llm_structured_mode: Literal["json_schema", "json_object", "prompt"] = "json_schema"
    # Таймаут одного запроса к LLM: внешние API отвечают неравномерно
    openai_timeout_seconds: float = 30.0
    # Повторы на уровне SDK: наш провайдер сам делает резервный запрос,
    # поэтому лишние ретраи только увеличивают худшее время ответа
    openai_max_retries: int = 0
    # CORS: браузерные источники, которым разрешены запросы (frontend dev-сервер)
    cors_origins: list[str] = ["http://localhost:5173"]
    # Agent Harness: лимиты цикла
    agent_max_steps: int = 10
    agent_token_budget: int = 50000
    agent_timeout_seconds: float = 120
    agent_tool_timeout_seconds: float = 30
    # Эмбеддинги для нормализации навыков: none (по умолчанию, только alias + нечёткое
    # совпадение), local (локальная ONNX-модель), mock (тесты)
    embedding_provider: str = "none"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # Порог косинусной близости, при котором навык сопоставляется с темой
    embedding_threshold: float = 0.35
    # Каталог кэша моделей (не коммитится)
    embedding_cache_dir: str = ".cache/fastembed"
    # Максимум новых provisional-тем на один документ. Если лимит исчерпан,
    # остальные незнакомые навыки попадают в одну тему «Новые навыки (на ревью)».
    # 0 — не создавать отдельные темы, сразу использовать review-тему.
    auto_topic_limit: int = 10
    # Автоматическое ревью provisional-тем после сохранения вакансии/резюме:
    # сначала дешёвые правила, затем LLM только для спорных тем. Ошибка ревью
    # не должна ломать загрузку документа, поэтому вызов выполняется best-effort.
    ontology_auto_review_enabled: bool = True
    # Минимальная уверенность LLM-решения, при которой оно применяется.
    # Ниже порога тема остаётся provisional и ждёт ручной проверки.
    ontology_auto_review_min_confidence: float = 0.75
    # Косинусная близость, при которой тема автоматически сливается с canonical.
    # Значение намеренно высокое: merge необратимо меняет связи.
    ontology_auto_merge_similarity: float = 0.9
    # Сколько упоминаний в разных документах достаточно для авто-подтверждения
    # темы без LLM. 1 — подтверждать уже после первого документа.
    ontology_auto_approve_min_documents: int = 2
    # Предохранитель против всплеска LLM-вызовов: сколько тем проверять за прогон.
    ontology_auto_review_max_topics: int = 20


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный экземпляр настроек (кэшируется)."""
    return Settings()
