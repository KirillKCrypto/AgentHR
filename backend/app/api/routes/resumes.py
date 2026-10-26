"""Эндпоинты резюме: загрузка текста, список и карточка."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, Embedder, LlmProvider
from app.api.mappers import resume_read
from app.models import Resume
from app.schemas.analysis import ResumeCreate, ResumeRead, ResumeSummary
from app.services.analysis import AnalysisError
from app.services.profile import NotFoundError, analyze_resume, get_resume, load_resume_skills

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_resume(
    payload: ResumeCreate,
    db: DbSession,
    provider: LlmProvider,
    embedder: Embedder,
    current_user: CurrentUser,
) -> ResumeRead:
    """Создаёт резюме, извлекает навыки и пересобирает профиль знаний."""
    try:
        resume = await analyze_resume(
            db,
            provider,
            current_user.id,
            raw_text=payload.raw_text,
            title=payload.title,
            embedder=embedder,
        )
    except AnalysisError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    skills = await load_resume_skills(db, resume.id)
    return resume_read(resume, skills)


@router.get("")
async def list_resumes(
    db: DbSession,
    current_user: CurrentUser,
) -> list[ResumeSummary]:
    """Резюме текущего пользователя (без навыков)."""
    resumes = (
        await db.scalars(
            select(Resume)
            .where(Resume.user_id == current_user.id)
            .order_by(Resume.created_at.desc())
        )
    ).all()
    return [ResumeSummary.model_validate(resume) for resume in resumes]


@router.get("/{resume_id}")
async def read_resume(
    resume_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ResumeRead:
    """Карточка резюме с извлечёнными навыками."""
    try:
        resume = await get_resume(db, current_user.id, resume_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    skills = await load_resume_skills(db, resume.id)
    return resume_read(resume, skills)
