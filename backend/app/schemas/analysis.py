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
    status: str = "canonical"


class SkillRead(BaseModel):
    """Навык документа вместе с сопоставленной темой."""

    id: UUID
    raw_name: str
    level: int = Field(description="Требуемый уровень (вакансия) или владение (резюме), 0..100")
    weight: float | None = Field(default=None, description="Важность навыка для вакансии, 0..1")
    confidence: float
    evidence: str | None = None
    match_method: str = Field(
        description=(
            "exact | alias | fuzzy | embedding | provisional | "
            "auto_approve | auto_merge | backfill | none"
        )
    )
    topic: TopicBrief | None = None
    requirement_group: str | None = None
    requirement_logic: str = "SINGLE"
    criticality: str = "must_have"


class VacancyRead(BaseModel):
    """Вакансия с извлечёнными навыками."""

    id: UUID
    user_id: UUID
    title: str | None = None
    company: str | None = None
    level: str | None = None
    raw_text: str
    created_at: datetime
    skills: list[SkillRead] = []
    reused: bool = False


class VacancySummary(BaseModel):
    """Вакансия для списка (без навыков и текста)."""

    id: UUID
    title: str | None = None
    company: str | None = None
    level: str | None = None
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
    is_active: bool = False
    reused: bool = False


class ResumeSummary(BaseModel):
    """Резюме для списка (без навыков и текста)."""

    id: UUID
    title: str | None = None
    created_at: datetime
    skills_count: int = 0
    is_active: bool = False

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
    evidence_type: str = "self_report"
    verified_level: int | None = None
    review_due_at: datetime | None = None
    review_interval_days: int = 1
    last_assessed: datetime | None = None
    status: str = "canonical"


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
    topic_status: str | None = None
    requirement_group: str | None = None
    requirement_logic: str = "SINGLE"
    criticality: str = "must_have"
    covered_by_alternative: bool = False
    self_level: int = Field(default=0, description="Уровень из резюме или ручной оценки")
    verified_level: int = Field(default=0, description="Уровень, подтверждённый тестом или интервью")
    verified_gap: int = Field(default=0, description="Разрыв по подтверждённому уровню")
    verified_satisfied: bool = Field(default=False, description="Навык закрыт подтверждённым уровнем")
    status: str = Field(
        default="unverified",
        description="confirmed | partial | self_only | unverified",
    )
    evidence_type: str = Field(default="none", description="test | interview | resume | manual | none")
    confidence: float = Field(default=0.0, ge=0, le=1)


class GapRecommendationRead(BaseModel):
    """Навык, который нужно подтянуть в первую очередь."""

    topic_key: str | None = None
    topic_name: str | None = None
    skill_name: str
    required_level: int
    user_level: int
    gap: int
    priority: float
    criticality: str
    reason: str


class GapBlockerRead(BaseModel):
    """Обязательное требование, которое мешает готовности."""

    skill_name: str
    topic_key: str | None = None
    topic_name: str | None = None
    required_level: int
    verified_level: int
    gap: int
    weight: float
    criticality: str = "must_have"


class GapConfirmationRead(BaseModel):
    """Навык, подтверждение которого уточнит расчёт готовности."""

    skill_name: str
    topic_key: str | None = None
    topic_name: str | None = None
    required_level: int
    self_level: int
    verified_level: int
    criticality: str = "must_have"
    potential_gain: float = Field(ge=0, le=1, description="Прирост verified readiness, 0..1")
    reason: str


class GapAnalysisRead(BaseModel):
    """Gap-анализ вакансии относительно профиля."""

    vacancy_id: UUID
    vacancy_title: str | None = None
    items: list[GapItemRead] = []
    overall_readiness: float = Field(
        description="Взвешенное покрытие всех требований, включая provisional, 0..1"
    )
    coverage_all: float = Field(description="Покрытие всех требований, включая provisional, 0..1")
    confirmed_readiness: float | None = Field(
        default=None,
        description="Покрытие только canonical-требований; null, если их нет",
    )
    critical_readiness: float | None = Field(
        default=None,
        description="Покрытие только must_have-требований; null, если их нет",
    )
    satisfied_count: int = Field(default=0, description="Сколько требований закрыто")
    requirements_count: int = Field(default=0, description="Сколько требований всего")
    average_gap: float = Field(default=0.0, description="Средневзвешенный разрыв в пунктах, 0..100")
    recommendations: list[GapRecommendationRead] = Field(
        default=[], description="Что подтянуть в первую очередь"
    )
    provisional_count: int = Field(description="Сколько требований опираются на provisional-темы")
    provisional_weight: float = Field(description="Суммарный вес provisional-требований")
    confirmed_weight: float = Field(description="Суммарный вес canonical-требований")
    critical_count: int = Field(description="Количество must_have-требований")
    critical_weight: float = Field(description="Суммарный вес must_have-требований")
    critical_gap_count: int = Field(description="Количество незакрытых must_have-требований")
    unmatched_count: int = Field(description="Навыков вакансии вне онтологии")
    readiness: float = Field(default=0.0, description="Готовность с критическим гейтом, 0..1")
    readiness_low: float = Field(default=0.0, description="Нижняя граница готовности, 0..1")
    readiness_high: float = Field(default=0.0, description="Верхняя граница готовности, 0..1")
    critical_gate: float = Field(default=1.0, description="Множитель критического гейта, 0..1")
    confidence: float = Field(default=0.0, description="Средняя уверенность требований, 0..1")
    potential_readiness: float = Field(
        default=0.0, description="Готовность по эффективному уровню, 0..1"
    )
    verified_readiness: float | None = Field(
        default=None, description="Готовность только по подтверждённым навыкам, 0..1"
    )
    critical_verified: float | None = Field(
        default=None, description="Закрытие must_have подтверждёнными навыками, 0..1"
    )
    evidence_coverage: float = Field(
        default=0.0, description="Доля веса требований с подтверждением, 0..1"
    )
    band: str = Field(default="not_ready", description="ready | almost | needs_confirmation | not_ready")
    band_reason: str = ""
    blockers: list[GapBlockerRead] = []
    confirmation_queue: list[GapConfirmationRead] = []


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
