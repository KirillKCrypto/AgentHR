"""ORM-модели плана подготовки: план и его темы."""

import uuid
from datetime import datetime

from sqlalchemy import (
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LearningPlan(Base):
    """Персональный план подготовки по темам из резюме."""

    __tablename__ = "learning_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Вакансия необязательна: план можно собрать только по профилю.
    vacancy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("vacancies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    # active | completed | archived
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default=text("'active'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<LearningPlan id={self.id} status={self.status!r}>"


class PlanItem(Base):
    """Тема плана с текущим и целевым уровнем."""

    __tablename__ = "plan_items"
    __table_args__ = (UniqueConstraint("plan_id", "topic_id", name="uq_plan_items_plan_topic"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("learning_plans.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topics.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    current_level: Mapped[int] = mapped_column(Integer, default=0)
    target_level: Mapped[int] = mapped_column(Integer, default=100)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    priority: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:
        return f"<PlanItem plan={self.plan_id} topic={self.topic_id}>"
