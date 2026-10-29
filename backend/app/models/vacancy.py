"""ORM-модели вакансий и извлечённых из них навыков."""

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


class Vacancy(Base):
    """Вакансия, загруженная пользователем."""

    __tablename__ = "vacancies"

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
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    # manual | file — источник загрузки
    source: Mapped[str] = mapped_column(
        String(20), default="manual", server_default=text("'manual'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Vacancy id={self.id} title={self.title!r}>"


class VacancySkill(Base):
    """Навык, извлечённый из вакансии.

    `topic_id` обязателен: неизвестный навык получает provisional-тему.
    """

    __tablename__ = "vacancy_skills"
    __table_args__ = (
        CheckConstraint(
            "required_level >= 0 AND required_level <= 100", name="ck_vacancy_skills_level"
        ),
        CheckConstraint("weight >= 0 AND weight <= 1", name="ck_vacancy_skills_weight"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_vacancy_skills_confidence"),
        CheckConstraint(
            "requirement_logic IN ('SINGLE', 'AND', 'OR')",
            name="ck_vacancy_skills_requirement_logic",
        ),
        CheckConstraint(
            "criticality IN ('must_have', 'nice_to_have')",
            name="ck_vacancy_skills_criticality",
        ),
        Index("ix_vacancy_skills_vacancy_topic", "vacancy_id", "topic_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("vacancies.id", ondelete="CASCADE"), index=True
    )
    # RESTRICT не даёт удалить тему, пока на неё ссылаются навыки.
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    raw_name: Mapped[str] = mapped_column(String(200))
    # Ожидаемый уровень владения, 0..100
    required_level: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Важность навыка для вакансии, 0..1
    weight: Mapped[float] = mapped_column(Float, default=1.0, server_default=text("1.0"))
    # Группа требований: одинаковый group объединяет альтернативы/конъюнкции.
    requirement_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # SINGLE | AND | OR
    requirement_logic: Mapped[str] = mapped_column(
        String(10), default="SINGLE", server_default=text("'SINGLE'")
    )
    # must_have | nice_to_have
    criticality: Mapped[str] = mapped_column(
        String(20), default="must_have", server_default=text("'must_have'")
    )
    # Уверенность извлечения, 0..1
    confidence: Mapped[float] = mapped_column(Float, default=0.5, server_default=text("0.5"))
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    # exact | alias | fuzzy | embedding | provisional | backfill | manual | none
    match_method: Mapped[str] = mapped_column(
        String(20), default="none", server_default=text("'none'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<VacancySkill {self.raw_name!r} topic_id={self.topic_id}>"
