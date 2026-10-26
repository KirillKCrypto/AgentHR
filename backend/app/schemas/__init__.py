"""Pydantic-схемы AgentHR."""

from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    GapAnalysisRead,
    GapItemRead,
    ProfileRead,
    ProfileTopicRead,
    ResumeCreate,
    ResumeRead,
    ResumeSummary,
    SkillRead,
    TopicBrief,
    UnmatchedSkillRead,
    VacancyCreate,
    VacancyRead,
    VacancySummary,
)
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)

__all__ = [
    "AnalysisRequest",
    "AnalysisResponse",
    "GapAnalysisRead",
    "GapItemRead",
    "LoginRequest",
    "ProfileRead",
    "ProfileTopicRead",
    "RefreshRequest",
    "RegisterRequest",
    "ResumeCreate",
    "ResumeRead",
    "ResumeSummary",
    "SkillRead",
    "TokenResponse",
    "TopicBrief",
    "UnmatchedSkillRead",
    "UserRead",
    "VacancyCreate",
    "VacancyRead",
    "VacancySummary",
]
