"""Pydantic-схемы плана подготовки."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PlanCreate(BaseModel):
    """Запрос на построение плана."""

    vacancy_id: UUID | None = None


class PlanItemRead(BaseModel):
    """Тема плана."""

    topic_id: UUID
    topic_key: str
    topic_name: str
    category: str | None = None
    current_level: int = Field(ge=0, le=100)
    target_level: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    priority: float
    reason: str


class PlanRead(BaseModel):
    """План подготовки с темами."""

    id: UUID
    user_id: UUID
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    title: str
    status: str
    created_at: datetime | None = None
    items: list[PlanItemRead] = []


class PlanSummaryRead(BaseModel):
    """Краткая карточка плана."""

    id: UUID
    title: str
    status: str
    vacancy_id: UUID | None = None
    topic_count: int
