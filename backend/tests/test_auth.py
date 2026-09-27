"""Интеграционные тесты аутентификации (требуется запущенная БД из infra/)."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import async_session_factory, engine
from app.main import app
from app.models import User

settings = get_settings()

PASSWORD = "correct-horse-battery-staple"


async def _database_available() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """HTTP-клиент к приложению; пропускает тесты при недоступной БД."""
    if not await _database_available():
        pytest.skip("PostgreSQL недоступен — интеграционные тесты пропущены")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    # Закрываем соединения пула, чтобы они не «перескакивали» между event loop'ами тестов
    await engine.dispose()


@pytest.fixture
async def cleanup_emails(client: AsyncClient) -> AsyncGenerator[list[str]]:
    """Собирает email созданных пользователей и удаляет их после теста."""
    emails: list[str] = []
    yield emails

    async with async_session_factory() as session:
        for email in emails:
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                await session.delete(user)
        await session.commit()


def _email() -> str:
    return f"auth-{uuid4().hex}@example.com"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: AsyncClient, email: str, password: str = PASSWORD) -> None:
    response = await client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201


async def _login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


async def test_register_returns_created_user(
    client: AsyncClient, cleanup_emails: list[str]
) -> None:
    email = _email()
    cleanup_emails.append(email)

    response = await client.post("/auth/register", json={"email": email, "password": PASSWORD})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert UUID(body["id"])
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_duplicate_email_returns_409(
    client: AsyncClient, cleanup_emails: list[str]
) -> None:
    email = _email()
    cleanup_emails.append(email)
    await _register(client, email)

    response = await client.post("/auth/register", json={"email": email, "password": PASSWORD})

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("not-an-email", PASSWORD),
        (_email(), "short"),
    ],
)
async def test_register_validates_input(
    client: AsyncClient, cleanup_emails: list[str], email: str, password: str
) -> None:
    cleanup_emails.append(email)

    response = await client.post("/auth/register", json={"email": email, "password": password})

    assert response.status_code == 422


async def test_login_returns_token_pair(
    client: AsyncClient, cleanup_emails: list[str]
) -> None:
    email = _email()
    cleanup_emails.append(email)
    await _register(client, email)

    body = await _login(client, email)

    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_with_wrong_password_returns_401(
    client: AsyncClient, cleanup_emails: list[str]
) -> None:
    email = _email()
    cleanup_emails.append(email)
    await _register(client, email)

    response = await client.post(
        "/auth/login", json={"email": email, "password": "wrong-password"}
    )

    assert response.status_code == 401


async def test_login_with_unknown_email_returns_401(client: AsyncClient) -> None:
    response = await client.post("/auth/login", json={"email": _email(), "password": PASSWORD})

    assert response.status_code == 401


async def test_me_returns_current_user(
    client: AsyncClient, cleanup_emails: list[str]
) -> None:
    email = _email()
    cleanup_emails.append(email)
    await _register(client, email)
    tokens = await _login(client, email)

    response = await client.get("/me", headers=_auth_header(tokens["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == email
    assert "password_hash" not in body


async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_with_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/me", headers=_auth_header("not-a-token"))

    assert response.status_code == 401


async def test_me_with_expired_token_returns_401(client: AsyncClient) -> None:
    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "access",
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get("/me", headers=_auth_header(expired))

    assert response.status_code == 401


async def test_me_rejects_refresh_token(
    client: AsyncClient, cleanup_emails: list[str]
) -> None:
    email = _email()
    cleanup_emails.append(email)
    await _register(client, email)
    tokens = await _login(client, email)

    response = await client.get("/me", headers=_auth_header(tokens["refresh_token"]))

    assert response.status_code == 401


async def test_refresh_returns_new_token_pair(
    client: AsyncClient, cleanup_emails: list[str]
) -> None:
    email = _email()
    cleanup_emails.append(email)
    await _register(client, email)
    tokens = await _login(client, email)

    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"]

    me_response = await client.get("/me", headers=_auth_header(new_tokens["access_token"]))
    assert me_response.status_code == 200


async def test_refresh_rejects_garbage(client: AsyncClient) -> None:
    response = await client.post("/auth/refresh", json={"refresh_token": "garbage"})

    assert response.status_code == 401
