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
    criticality: str = "nice_to_have"
    confidence: float = Field(ge=0, le=1)
    priority: float
    reason: str
    question_count: int = 0


class PlanRead(BaseModel):
    """План подготовки с темами."""

    id: UUID
    user_id: UUID
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    resume_id: UUID | None = None
    resume_title: str | None = None
    title: str
    status: str
    kind: str = "general"
    created_at: datetime | None = None
    reused: bool = False
    items: list[PlanItemRead] = []


class PlanSummaryRead(BaseModel):
    """Краткая карточка плана."""

    id: UUID
    title: str
    status: str
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    resume_id: UUID | None = None
    topic_count: int
    kind: str = "general"
    created_at: datetime | None = None
    is_current: bool = False


class QuestionRead(BaseModel):
    """Вопрос банка."""

    id: UUID
    topic_id: UUID
    difficulty: int
    text: str
    expected_points: list[str] = []
    source: str
