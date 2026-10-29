"""Аудит ревью онтологии: approve, reject, merge и keep provisional-тем."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OntologyReviewAction(Base):
    """История ручных и автоматических действий над темами онтологии."""

    __tablename__ = "ontology_review_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # approve | reject | merge | keep
    action: Mapped[str] = mapped_column(String(20))
    source_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(120), default="cli", server_default=text("'cli'"))
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<OntologyReviewAction {self.action} source={self.source_topic_id}>"
