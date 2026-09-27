"""Интеграционный тест модели User (требуется запущенная БД из infra/)."""

from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import async_session_factory, engine
from app.models import User


async def _database_available() -> bool:
    """Проверяет доступность БД, чтобы пропустить тест без запущенного Postgres."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True


async def test_user_insert_and_read() -> None:
    """Пользователь вставляется в БД и читается обратно."""
    if not await _database_available():
        pytest.skip("PostgreSQL недоступен — интеграционный тест пропущен")

    email = f"test-{uuid4().hex}@example.com"
    try:
        async with async_session_factory() as session:
            user = User(email=email, password_hash="test-hash")
            session.add(user)
            await session.commit()
            await session.refresh(user)

            fetched = await session.get(User, user.id)

            assert fetched is not None
            assert fetched.email == email
            assert fetched.created_at is not None
    finally:
        # Убираем тестовые данные и закрываем соединения пула перед завершением цикла
        async with async_session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                await session.delete(user)
                await session.commit()
        await engine.dispose()
