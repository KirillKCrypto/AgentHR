"""Общие фикстуры интеграционных тестов: БД, HTTP-клиент и заглушка LLM."""

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_embedder, get_llm_provider
from app.db.session import async_session_factory, engine
from app.llm.base import (
    ChatMessage,
    LLMError,
    LLMResponse,
    StructuredResult,
    ToolSpec,
)
from app.main import app
from app.models import User
from app.ontology.seed import seed_ontology

PASSWORD = "correct-horse-battery-staple"

VACANCY_TEXT = (
    "Ищем Python-разработчика. Опыт Python от 3 лет, знание PostgreSQL, "
    "Kafka будет плюсом."
)
RESUME_TEXT = "3 года на Python. Писал SQL-запросы. Собирал Docker-образы."

VACANCY_DATA: dict[str, Any] = {
    "title": "Python-разработчик",
    "company": "Acme",
    "level": "middle",
    "skills": [
        {
            "name": "Python",
            "required_level": 70,
            "weight": 1.0,
            "evidence": "Опыт Python от 3 лет",
            "confidence": 0.9,
        },
        {
            "name": "PostgreSQL",
            "required_level": 60,
            "weight": 0.8,
            "evidence": "Знание PostgreSQL",
            "confidence": 0.85,
        },
        {
            "name": "Kafka",
            "required_level": 40,
            "weight": 0.3,
            "evidence": "Kafka как плюс",
            "confidence": 0.6,
        },
    ],
}

RESUME_DATA: dict[str, Any] = {
    "experience_years": 3.0,
    "self_level": "middle",
    "skills": [
        {
            "name": "Python",
            "proficiency": 75,
            "evidence": "3 года на Python",
            "confidence": 0.9,
        },
        {
            "name": "SQL",
            "proficiency": 50,
            "evidence": "писал запросы",
            "confidence": 0.7,
        },
        {
            "name": "Docker",
            "proficiency": 40,
            "evidence": "собирал образы",
            "confidence": 0.6,
        },
    ],
}


class SchemaStubProvider:
    """LLM-заглушка: отдаёт заготовленный ответ по имени JSON-схемы."""

    def __init__(self, responses: dict[str, dict[str, Any]] | None = None) -> None:
        self.responses = responses or {
            "vacancy_requirements": VACANCY_DATA,
            "resume_skills": RESUME_DATA,
        }
        self.calls: list[str] = []

    async def generate_with_tools(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> LLMResponse:
        """Заглушка не поддерживает вызовы инструментов."""
        raise LLMError("SchemaStubProvider: generate_with_tools не поддерживается")

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: dict[str, Any],
        *,
        schema_name: str = "result",
    ) -> StructuredResult:
        """Возвращает ответ, привязанный к имени схемы."""
        self.calls.append(schema_name)
        if schema_name not in self.responses:
            raise LLMError(f"SchemaStubProvider: нет ответа для схемы {schema_name!r}")
        return StructuredResult(data=self.responses[schema_name])

    async def close(self) -> None:
        """Ресурсов нет."""
        return


async def database_available() -> bool:
    """Проверяет доступность PostgreSQL."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True


@pytest.fixture
async def seeded_db() -> AsyncGenerator[None]:
    """Пропускает тест без БД и гарантирует засеянную онтологию."""
    if not await database_available():
        pytest.skip("PostgreSQL недоступен — интеграционный тест пропущен")

    async with async_session_factory() as session:
        await seed_ontology(session)

    yield

    await engine.dispose()


@dataclass
class ApiUser:
    """Зарегистрированный пользователь и его HTTP-клиент."""

    client: AsyncClient
    headers: dict[str, str]
    user_id: str
    email: str
    provider: SchemaStubProvider = field(default_factory=SchemaStubProvider)


async def _register_user(
    client: AsyncClient, *, provider: SchemaStubProvider | None = None
) -> ApiUser:
    """Регистрирует пользователя через API и возвращает его контекст."""
    email = f"analysis-{uuid4().hex}@example.com"
    response = await client.post(
        "/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()["access_token"]

    return ApiUser(
        client=client,
        headers={"Authorization": f"Bearer {token}"},
        user_id=user_id,
        email=email,
        provider=provider or SchemaStubProvider(),
    )


@pytest.fixture
async def api_user(seeded_db: None) -> AsyncGenerator[ApiUser]:
    """Пользователь с подменёнными LLM и эмбеддером."""
    stub = SchemaStubProvider()
    app.dependency_overrides[get_llm_provider] = lambda: stub
    app.dependency_overrides[get_embedder] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user = await _register_user(client, provider=stub)
        yield user

        async with async_session_factory() as session:
            existing = await session.scalar(select(User).where(User.email == user.email))
            if existing is not None:
                await session.delete(existing)
                await session.commit()

    app.dependency_overrides.clear()


@pytest.fixture
async def second_user(api_user: ApiUser) -> ApiUser:
    """Второй пользователь в том же приложении (проверка изоляции)."""
    user = await _register_user(api_user.client)
    yield user

    async with async_session_factory() as session:
        existing = await session.scalar(select(User).where(User.email == user.email))
        if existing is not None:
            await session.delete(existing)
            await session.commit()
