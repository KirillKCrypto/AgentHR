"""Хеширование паролей и выпуск/проверка JWT."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

settings = get_settings()

TokenType = Literal["access", "refresh"]

# argon2id — memory-hard хеширование паролей
_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Возвращает argon2-хеш пароля."""
    return _password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Проверяет пароль против сохранённого хеша."""
    return _password_hasher.verify(password, hashed_password)


def create_token(user_id: uuid.UUID, token_type: TokenType) -> str:
    """Выпускает подписанный JWT заданного типа."""
    now = datetime.now(UTC)
    if token_type == "access":
        lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    else:
        lifetime = timedelta(days=settings.refresh_token_expire_days)

    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType) -> uuid.UUID:
    """Проверяет токен и возвращает id пользователя.

    Raises:
        jwt.InvalidTokenError: токен невалиден, просрочен или неверного типа.
    """
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")

    try:
        return uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise jwt.InvalidTokenError("Invalid subject") from exc
