"""ORM-модели мини-тестов для подтверждения уровня навыков."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssessmentQuestion(Base):
    """Вопрос банка assessment по конкретной теме."""

    __tablename__ = "assessment_questions"
    __table_args__ = (
        CheckConstraint(
            "difficulty >= 0 AND difficulty <= 100",
            name="ck_assessment_questions_difficulty",
        ),
        UniqueConstraint("key", name="uq_assessment_questions_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    key: Mapped[str] = mapped_column(String(100), index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    difficulty: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(
        String(30), default="single_choice", server_default=text("'single_choice'")
    )
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    correct_key: Mapped[str] = mapped_column(String(20))
    explanation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default=text("'active'")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<AssessmentQuestion {self.key} topic={self.topic_id}>"


class AssessmentAttempt(Base):
    """Попытка прохождения теста по одной теме."""

    __tablename__ = "assessment_attempts"
    __table_args__ = (
        Index(
            "uq_assessment_attempt_completed",
            "user_id",
            "topic_id",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="in_progress", server_default=text("'in_progress'")
    )
    question_ids: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    test_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<AssessmentAttempt {self.id} user={self.user_id} status={self.status}>"


class AssessmentAnswer(Base):
    """Ответ пользователя на вопрос попытки."""

    __tablename__ = "assessment_answers"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id", "question_id", name="uq_assessment_answers_attempt_question"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assessment_attempts.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assessment_questions.id", ondelete="CASCADE"), index=True
    )
    answer_key: Mapped[str] = mapped_column(String(20))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<AssessmentAnswer attempt={self.attempt_id} correct={self.is_correct}>"
