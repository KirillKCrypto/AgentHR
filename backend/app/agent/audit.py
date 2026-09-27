"""Аудит-лог действий агента (таблица `agent_actions`)."""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AgentAction


@dataclass(frozen=True)
class AgentActionRecord:
    """Одна запись аудит-лога действий агента."""

    session_id: uuid.UUID | None
    step: int
    status: str
    duration_ms: int
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    result: Any = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class AuditLogger(Protocol):
    """Интерфейс аудит-логгера."""

    async def log(self, record: AgentActionRecord) -> None:
        """Сохраняет запись аудит-лога."""
        ...


class InMemoryAuditLogger:
    """Хранит записи в памяти (тесты без БД)."""

    def __init__(self) -> None:
        self.records: list[AgentActionRecord] = []

    async def log(self, record: AgentActionRecord) -> None:
        self.records.append(record)


class DbAuditLogger:
    """Пишет записи в таблицу `agent_actions`."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def log(self, record: AgentActionRecord) -> None:
        async with self._session_factory() as session:
            session.add(
                AgentAction(
                    session_id=record.session_id,
                    step=record.step,
                    tool_name=record.tool_name,
                    arguments=record.arguments,
                    result=record.result,
                    status=record.status,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    duration_ms=record.duration_ms,
                )
            )
            await session.commit()
