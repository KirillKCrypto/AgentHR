"""Pydantic-схемы интервью."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class InterviewCreate(BaseModel):
    """Запрос на создание интервью по конкретной вакансии."""

    vacancy_id: UUID


class InterviewTurnRead(BaseModel):
    """Вопрос интервью и результат ответа."""

    id: UUID
    position: int
    topic_id: UUID
    topic_key: str
    topic_name: str
    question_text: str
    context: str | None = None
    kind: str = "base"
    parent_turn_id: UUID | None = None
    difficulty: int
    status: str
    answer_text: str | None = None
    score: float | None = None
    verdict: str | None = None
    feedback: str | None = None
    covered_points: list[str] = []
    missed_points: list[str] = []
    score_breakdown: dict[str, Any] | None = None
    answered_at: datetime | None = None


class InterviewRead(BaseModel):
    """Сессия интервью."""

    id: UUID
    user_id: UUID
    plan_id: UUID | None = None
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    title: str
    status: str
    score: float | None = None
    level: int | None = None
    question_count: int
    max_questions: int = 8
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
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    score: float | None = None
    question_count: int
    max_questions: int = 8
    answered_count: int
    created_at: datetime
    finished_at: datetime | None = None


class InterviewReportTopicRead(BaseModel):
    """Тема в итоговом отчёте интервью."""

    topic_key: str
    topic_name: str
    score: float | None = None
    missed_points: list[str] = []


class InterviewReportRead(BaseModel):
    """Итоги завершённого интервью."""

    interview_id: UUID
    status: str
    score: float | None = None
    level: int | None = None
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    finished_at: datetime | None = None
    question_count: int = 0
    answered_count: int = 0
    dimensions: dict[str, float] = {}
    previous_score: float | None = None
    delta: float | None = None
    strengths: list[InterviewReportTopicRead] = []
    improvements: list[InterviewReportTopicRead] = []
    untouched: list[InterviewReportTopicRead] = []


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
