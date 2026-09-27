"""ORM-модель аудит-лога действий агента."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentAction(Base):
    """Запись аудит-лога: шаг агента, tool, аргументы, результат, токены, время."""

    __tablename__ = "agent_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # Без FK: сессии интервью появятся на неделе 5, до тех пор id сессии свободный
    session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    step: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str | None] = mapped_column(String(100))
    arguments: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    result: Mapped[Any] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
