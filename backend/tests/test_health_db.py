"""Тесты эндпоинта /health/db (БД подменяется через dependency_overrides)."""

from collections.abc import AsyncGenerator, Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.main import app

client = TestClient(app)


class FakeSession:
    """Заглушка сессии: execute успешен."""

    async def execute(self, *args: object, **kwargs: object) -> None:
        """Имитирует успешный SELECT 1."""


class FailingSession:
    """Заглушка сессии: execute падает с ошибкой SQLAlchemy."""

    async def execute(self, *args: object, **kwargs: object) -> None:
        """Имитирует ошибку выполнения запроса."""
        raise SQLAlchemyError("connection failed")


class UnreachableSession:
    """Заглушка сессии: соединение не устанавливается."""

    async def execute(self, *args: object, **kwargs: object) -> None:
        """Имитирует недоступность сервера БД (connection refused)."""
        raise OSError("connection refused")


async def _override_ok() -> AsyncGenerator[FakeSession]:
    yield FakeSession()


async def _override_fail() -> AsyncGenerator[FailingSession]:
    yield FailingSession()


async def _override_unreachable() -> AsyncGenerator[UnreachableSession]:
    yield UnreachableSession()


def test_health_db_returns_ok() -> None:
    """GET /health/db отвечает 200, когда БД доступна."""
    app.dependency_overrides[get_db] = _override_ok
    try:
        response = client.get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.parametrize("override", [_override_fail, _override_unreachable])
def test_health_db_returns_503_when_database_unavailable(
    override: Callable[..., AsyncGenerator[object]],
) -> None:
    """GET /health/db отвечает 503 при ошибке запроса или соединения с БД."""
    app.dependency_overrides[get_db] = override
    try:
        response = client.get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
