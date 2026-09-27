"""Интеграционный тест DbAuditLogger (требуется запущенная БД)."""

from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.agent import AgentActionRecord, DbAuditLogger
from app.db.session import async_session_factory, engine
from app.models import AgentAction


async def _database_available() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True


async def test_db_audit_logger_writes_record() -> None:
    if not await _database_available():
        pytest.skip("PostgreSQL недоступен — интеграционный тест пропущен")

    session_id = uuid4()
    logger = DbAuditLogger(async_session_factory)
    try:
        await logger.log(
            AgentActionRecord(
                session_id=session_id,
                step=1,
                status="success",
                duration_ms=12,
                tool_name="ping",
                arguments={"x": 1},
                result={"ok": True},
                input_tokens=10,
                output_tokens=5,
            )
        )

        async with async_session_factory() as session:
            action = await session.scalar(
                select(AgentAction).where(AgentAction.session_id == session_id)
            )

        assert action is not None
        assert action.tool_name == "ping"
        assert action.arguments == {"x": 1}
        assert action.result == {"ok": True}
        assert action.input_tokens == 10
        assert action.duration_ms == 12
    finally:
        async with async_session_factory() as session:
            action = await session.scalar(
                select(AgentAction).where(AgentAction.session_id == session_id)
            )
            if action is not None:
                await session.delete(action)
                await session.commit()
        await engine.dispose()
