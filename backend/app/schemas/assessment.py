"""Pydantic-схемы мини-тестов навыков."""

from uuid import UUID

from pydantic import BaseModel


class AssessmentOption(BaseModel):
    """Вариант ответа."""

    key: str
    text: str


class AssessmentTopicRead(BaseModel):
    """Доступная тема теста и статус прохождения."""

    topic_key: str
    topic_name: str
    question_count: int
    completed: bool = False
    test_level: int | None = None
    attempt_id: UUID | None = None


class AssessmentQuestionRead(BaseModel):
    """Вопрос без правильного ответа."""

    id: UUID
    difficulty: int
    kind: str
    prompt: str
    options: list[AssessmentOption]


class AssessmentStartRead(BaseModel):
    """Старт попытки."""

    attempt_id: UUID
    topic_key: str
    topic_name: str
    questions: list[AssessmentQuestionRead]


class AssessmentAnswerRequest(BaseModel):
    """Ответ на вопрос."""

    question_id: UUID
    answer_key: str


class AssessmentAnswerRead(BaseModel):
    """Прогресс попытки."""

    question_id: UUID
    answered_count: int
    total: int


class AssessmentResultItem(BaseModel):
    """Разбор одного вопроса."""

    question_id: UUID
    prompt: str
    answer_key: str | None = None
    correct_key: str
    is_correct: bool
    explanation: str


class AssessmentFinishRead(BaseModel):
    """Результат теста."""

    attempt_id: UUID
    topic_key: str | None = None
    topic_name: str | None = None
    test_level: int
    confidence: float
    score: float
    correct_count: int
    total: int
    items: list[AssessmentResultItem]
