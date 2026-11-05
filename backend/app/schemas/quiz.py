"""Pydantic-схемы теста по теме."""

from uuid import UUID

from pydantic import BaseModel, Field


class QuizQuestionRead(BaseModel):
    """Вопрос теста без правильного ответа."""

    id: UUID
    difficulty: int
    text: str
    options: list[str]


class QuizRead(BaseModel):
    """Тест по теме."""

    topic_key: str
    topic_name: str
    questions: list[QuizQuestionRead] = []


class QuizStartRequest(BaseModel):
    """Запрос теста по теме."""

    topic_key: str = Field(min_length=1, max_length=64)
    count: int = Field(default=10, ge=5, le=20)


class QuizAnswer(BaseModel):
    """Ответ пользователя на вопрос."""

    question_id: UUID
    selected_option: int = Field(ge=0, le=3)


class QuizGradeRequest(BaseModel):
    """Ответы пользователя для проверки."""

    topic_key: str = Field(min_length=1, max_length=64)
    answers: list[QuizAnswer] = Field(min_length=1)


class QuizResultItemRead(BaseModel):
    """Разбор одного вопроса."""

    question_id: UUID
    text: str
    difficulty: int
    options: list[str]
    selected_option: int
    correct_option: int
    is_correct: bool
    explanation: str | None = None
    expected_points: list[str] = []


class QuizResultRead(BaseModel):
    """Итог теста."""

    topic_key: str
    topic_name: str
    score: float = Field(ge=0, le=1, description="Взвешенная доля правильных ответов")
    level: int = Field(ge=0, le=100, description="Оценка знания темы 0..100")
    correct_count: int
    total: int
    items: list[QuizResultItemRead] = []
