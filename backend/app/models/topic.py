"""ORM-модели графа знаний: темы, зависимости и кандидаты тем."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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


class Topic(Base):
    """Тема онтологии — узел графа знаний.

    Тема — словарь верхнего уровня для графа и планирования, а не фильтр:
    навыки, для которых темы нет, сохраняются отдельно (см. `TopicCandidate`).
    """

    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # Стабильный ключ (слаг) — по нему темы сопоставляются между собой
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    # Описание используется как текст для эмбеддингов при нормализации навыков
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Синонимы и альтернативные названия (для точного сопоставления)
    aliases: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    ontology_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    # Тема создана автоматически из кандидата и ещё не прошла ревью
    is_auto_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Topic key={self.key!r} name={self.name!r}>"


class TopicPrerequisite(Base):
    """Ребро `REQUIRES`: тема требует знания пререквизита."""

    __tablename__ = "topic_prerequisites"
    __table_args__ = (
        CheckConstraint("topic_id <> prerequisite_id", name="ck_topic_prerequisites_not_self"),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
    )
    prerequisite_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
    )

    def __repr__(self) -> str:
        return f"<TopicPrerequisite {self.topic_id} requires {self.prerequisite_id}>"


class TopicCandidate(Base):
    """Навык, для которого в онтологии нет темы: кандидат на новую тему.

    Кандидаты копятся по частоте появления в вакансиях и резюме — из них
    формируется пул тем на ревью (см. `AGENTS.md` §4, риск «качество онтологии»).
    """

    __tablename__ = "topic_candidates"
    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_topic_candidates_normalized_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # Название как в исходном тексте
    name: Mapped[str] = mapped_column(String(200))
    # Нормализованное название (lower + trim) — для агрегации и уникальности
    normalized_name: Mapped[str] = mapped_column(String(200), index=True)
    suggested_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Сколько раз встречался в источниках
    occurrences: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    # Список источников: [{"type": "vacancy", "id": "...", "evidence": "..."}]
    sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    # new | approved | rejected | merged
    status: Mapped[str] = mapped_column(String(20), default="new", server_default=text("'new'"))
    ontology_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<TopicCandidate {self.normalized_name!r} occurrences={self.occurrences}>"
