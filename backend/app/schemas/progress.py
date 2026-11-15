"""Pydantic-схемы дашборда и прогресса."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardProfileRead(BaseModel):
    """Сводка профиля знаний."""

    topics_count: int
    confirmed_count: int


class DashboardFocusTopicRead(BaseModel):
    """Тема в фокусе развития."""

    topic_key: str | None = None
    topic_name: str | None = None
    skill_name: str
    current_level: int
    required_level: int
    gap: int
    criticality: str = "must_have"


class DashboardVacancyRead(BaseModel):
    """Готовность к выбранной вакансии."""

    id: UUID
    title: str | None = None
    company: str | None = None
    coverage: float
    critical_readiness: float | None = None
    average_gap: float
    requirements_count: int
    satisfied_count: int
    critical_gap_count: int
    focus_topics: list[DashboardFocusTopicRead] = []


class DashboardInterviewRead(BaseModel):
    """Последнее интервью и его динамика."""

    id: UUID
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    score: float | None = None
    level: int | None = None
    finished_at: datetime | None = None
    delta: float | None = None


class DashboardHistoryRead(BaseModel):
    """Короткая история интервью."""

    id: UUID
    vacancy_title: str | None = None
    score: float | None = None
    level: int | None = None
    finished_at: datetime | None = None


class DashboardPlanRead(BaseModel):
    """Прогресс активного плана."""

    id: UUID
    title: str
    topic_count: int
    progress: float
    completed_count: int
    remaining_count: int


class DashboardActiveInterviewRead(BaseModel):
    """Незавершённое интервью."""

    id: UUID
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    answered_count: int
    max_questions: int
    started_at: datetime | None = None


class DashboardTestsRead(BaseModel):
    """Сводка тестов по темам."""

    completed_count: int
    average_level: float | None = None


class DashboardActivityRead(BaseModel):
    """Счётчики активности."""

    interviews_completed: int
    tests_completed: int
    active_plans: int


class DashboardRead(BaseModel):
    """Полный снимок дашборда."""

    profile: DashboardProfileRead
    vacancy: DashboardVacancyRead | None = None
    last_interview: DashboardInterviewRead | None = None
    active_interview: DashboardActiveInterviewRead | None = None
    interview_history: list[DashboardHistoryRead] = []
    plan: DashboardPlanRead | None = None
    tests: DashboardTestsRead
    activity: DashboardActivityRead


class PlanProgressItemRead(BaseModel):
    """Прогресс одной темы плана."""

    topic_id: UUID
    topic_key: str
    topic_name: str
    current_level: int = Field(ge=0, le=100)
    target_level: int = Field(ge=0, le=100)
    progress: float = Field(ge=0, le=1)
    completed: bool
    test_level: int | None = None
    interview_score: float | None = None


class PlanProgressRead(BaseModel):
    """Прогресс плана подготовки."""

    plan_id: UUID
    progress: float = Field(ge=0, le=1)
    topics_total: int
    completed_count: int
    remaining_count: int
    items: list[PlanProgressItemRead] = []
