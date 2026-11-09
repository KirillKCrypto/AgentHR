"""Pydantic-схемы интервью."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class InterviewCreate(BaseModel):
    """Запрос на создание интервью."""

    plan_id: UUID


class InterviewTurnRead(BaseModel):
    """Вопрос интервью и результат ответа."""

    id: UUID
    position: int
    topic_id: UUID
    topic_key: str
    topic_name: str
    question_text: str
    difficulty: int
    status: str
    answer_text: str | None = None
    score: float | None = None
    verdict: str | None = None
    feedback: str | None = None
    covered_points: list[str] = []
    missed_points: list[str] = []
    answered_at: datetime | None = None


class InterviewRead(BaseModel):
    """Сессия интервью."""

    id: UUID
    user_id: UUID
    plan_id: UUID | None = None
    title: str
    status: str
    score: float | None = None
    level: int | None = None
    question_count: int
    answered_count: int
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    turns: list[InterviewTurnRead] = []


class InterviewSummaryRead(BaseModel):
    """Краткая карточка интервью."""

    id: UUID
    title: str
    status: str
    level: int | None = None
    question_count: int
    answered_count: int
    created_at: datetime


class InterviewAnswerRequest(BaseModel):
    """Ответ на текущий вопрос."""

    turn_id: UUID
    answer_text: str = Field(min_length=1, max_length=5000)


class InterviewAnswerRead(BaseModel):
    """Результат ответа."""

    turn: InterviewTurnRead
    next_turn: InterviewTurnRead | None = None
    session: InterviewRead
    finished: bool
