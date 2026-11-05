"""ORM-модель банка вопросов для тренировок."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Question(Base):
    """Вопрос банка по теме и сложности."""

    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_topic_difficulty", "topic_id", "difficulty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topics.id", ondelete="RESTRICT"), index=True
    )
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    text: Mapped[str] = mapped_column(Text)
    # Эталонные пункты ответа: список строк.
    expected_points: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=sa_text("'[]'::jsonb")
    )
    # llm | manual | seed
    source: Mapped[str] = mapped_column(
        String(20), default="llm", server_default=sa_text("'llm'")
    )
    # Хеш темы, сложности и нормализованного текста — защита от дублей.
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Question topic={self.topic_id} difficulty={self.difficulty}>"
