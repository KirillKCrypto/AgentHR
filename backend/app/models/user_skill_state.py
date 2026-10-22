"""ORM-модель среза профиля знаний пользователя."""

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
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserSkillState(Base):
    """Материализованный срез графа знаний для пользователя.

    По паре (user_id, topic_id) хранится текущая оценка владения темой,
    уверенность оценки, её источник и доказательства (evidence).
    """

    __tablename__ = "user_skill_states"
    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_user_skill_states_user_topic"),
        CheckConstraint(
            "proficiency >= 0 AND proficiency <= 100", name="ck_user_skill_states_proficiency"
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_user_skill_states_confidence"
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
    # Оценка владения темой, 0..100
    proficiency: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Уверенность оценки, 0..1
    confidence: Mapped[float] = mapped_column(Float, default=0.5, server_default=text("0.5"))
    # resume | interview | manual | assessment
    source: Mapped[str] = mapped_column(
        String(30), default="resume", server_default=text("'resume'")
    )
    # Доказательства оценки: [{"type": "...", "text": "...", "weight": 1.0}]
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    last_assessed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<UserSkillState user={self.user_id} topic={self.topic_id} level={self.proficiency}>"
        )
