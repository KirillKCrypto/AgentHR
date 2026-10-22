"""ORM-модели резюме и извлечённых из них навыков."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Resume(Base):
    """Резюме пользователя (в MVP — введённый текстом)."""

    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Resume id={self.id} title={self.title!r}>"


class ResumeSkill(Base):
    """Навык, извлечённый из резюме.

    `topic_id` может быть NULL — навык сохранён как есть и показан в профиле
    отдельным блоком «вне онтологии».
    """

    __tablename__ = "resume_skills"
    __table_args__ = (
        CheckConstraint(
            "proficiency >= 0 AND proficiency <= 100", name="ck_resume_skills_proficiency"
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_resume_skills_confidence"),
        Index("ix_resume_skills_resume_topic", "resume_id", "topic_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("resumes.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    raw_name: Mapped[str] = mapped_column(String(200))
    # Оценка владения, 0..100
    proficiency: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Уверенность извлечения, 0..1
    confidence: Mapped[float] = mapped_column(Float, default=0.5, server_default=text("0.5"))
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    # exact | alias | fuzzy | embedding | manual | none
    match_method: Mapped[str] = mapped_column(
        String(20), default="none", server_default=text("'none'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<ResumeSkill {self.raw_name!r} topic_id={self.topic_id}>"
