"""ORM-модели сессии интервью и её вопросов."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
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


class InterviewSession(Base):
    """Сессия тренировочного интервью по плану подготовки."""

    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("learning_plans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vacancy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("vacancies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    # in_progress | completed
    status: Mapped[str] = mapped_column(
        String(20), default="in_progress", server_default=text("'in_progress'")
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    # Бюджет вопросов: база + follow-up.
    max_questions: Mapped[int] = mapped_column(Integer, default=8, server_default=text("8"))
    # Очередь тем: [{topic_id, current, target, context}, ...]
    topic_plan: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<InterviewSession id={self.id} status={self.status!r}>"


class InterviewTurn(Base):
    """Вопрос интервью, ответ пользователя и разбор."""

    __tablename__ = "interview_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "position", name="uq_interview_turns_position"),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="ck_interview_turns_score"),
        CheckConstraint(
            "difficulty >= 1 AND difficulty <= 5", name="ck_interview_turns_difficulty"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topics.id", ondelete="RESTRICT"), index=True
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("questions.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    question_text: Mapped[str] = mapped_column(Text)
    # Контекст из вакансии: исходное требование и evidence.
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    # base | follow_up
    kind: Mapped[str] = mapped_column(
        String(20), default="base", server_default=text("'base'")
    )
    parent_turn_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("interview_turns.id", ondelete="SET NULL"),
        nullable=True,
    )
    expected_points: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    # pending | answered
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default=text("'pending'")
    )
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    covered_points: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    missed_points: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<InterviewTurn session={self.session_id} position={self.position}>"
