"""Pydantic-схемы анализа вакансий, резюме и профиля знаний."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MAX_DOCUMENT_LENGTH = 50_000


class VacancyCreate(BaseModel):
    """Тело запроса на создание вакансии."""

    title: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    raw_text: str = Field(min_length=1, max_length=MAX_DOCUMENT_LENGTH)


class ResumeCreate(BaseModel):
    """Тело запроса на создание резюме."""

    title: str | None = Field(default=None, max_length=200)
    raw_text: str = Field(min_length=1, max_length=MAX_DOCUMENT_LENGTH)


class TopicBrief(BaseModel):
    """Краткое описание темы онтологии."""

    id: UUID
    key: str
    name: str
    category: str | None = None


class SkillRead(BaseModel):
    """Навык документа вместе с сопоставленной темой."""

    id: UUID
    raw_name: str
    level: int = Field(description="Требуемый уровень (вакансия) или владение (резюме), 0..100")
    weight: float | None = Field(default=None, description="Важность навыка для вакансии, 0..1")
    confidence: float
    evidence: str | None = None
    match_method: str = Field(description="exact | alias | fuzzy | embedding | none")
    topic: TopicBrief | None = None


class VacancyRead(BaseModel):
    """Вакансия с извлечёнными навыками."""

    id: UUID
    user_id: UUID
    title: str | None = None
    company: str | None = None
    raw_text: str
    created_at: datetime
    skills: list[SkillRead] = []


class VacancySummary(BaseModel):
    """Вакансия для списка (без навыков и текста)."""

    id: UUID
    title: str | None = None
    company: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeRead(BaseModel):
    """Резюме с извлечёнными навыками."""

    id: UUID
    user_id: UUID
    title: str | None = None
    raw_text: str
    created_at: datetime
    skills: list[SkillRead] = []


class ResumeSummary(BaseModel):
    """Резюме для списка (без навыков и текста)."""

    id: UUID
    title: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfileTopicRead(BaseModel):
    """Тема в срезе профиля знаний."""

    topic_id: UUID
    topic_key: str
    topic_name: str
    category: str | None = None
    proficiency: int
    confidence: float
    source: str
    last_assessed: datetime | None = None


class UnmatchedSkillRead(BaseModel):
    """Навык из резюме вне онтологии."""

    raw_name: str
    level: int
    confidence: float
    evidence: str | None = None
    match_method: str


class ProfileRead(BaseModel):
    """Профиль знаний пользователя."""

    user_id: UUID
    topics: list[ProfileTopicRead] = []
    unmatched_skills: list[UnmatchedSkillRead] = []


class GapItemRead(BaseModel):
    """Разрыв по одному навыку вакансии."""

    skill_name: str
    required_level: int
    user_level: int
    gap: int
    satisfied: bool
    weight: float
    topic_key: str | None = None
    topic_name: str | None = None


class GapAnalysisRead(BaseModel):
    """Gap-анализ вакансии относительно профиля."""

    vacancy_id: UUID
    vacancy_title: str | None = None
    items: list[GapItemRead] = []
    overall_readiness: float = Field(description="Доля закрытых требований, 0..1")
    unmatched_count: int = Field(description="Навыков вакансии вне онтологии")


class AnalysisRequest(BaseModel):
    """Запрос на совместный анализ вакансии и резюме."""

    vacancy_id: UUID
    resume_id: UUID


class AnalysisResponse(BaseModel):
    """Результат анализа: документы, профиль и разрывы."""

    vacancy: VacancyRead
    resume: ResumeRead
    profile: ProfileRead
    gaps: GapAnalysisRead
