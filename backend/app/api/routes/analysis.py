"""Совместный анализ вакансии и резюме: профиль и разрывы одним ответом."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.api.mappers import gap_analysis_read, profile_read, resume_read, vacancy_read
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.profile import (
    NotFoundError,
    compute_gaps,
    get_profile,
    get_resume,
    get_vacancy,
    load_resume_skills,
    load_vacancy_skills,
)

router = APIRouter(tags=["analysis"])


@router.post("/analysis")
async def analyze_documents(
    payload: AnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> AnalysisResponse:
    """Собирает анализ по уже загруженным вакансии и резюме.

    Извлечение навыков выполняется при загрузке документов
    (`POST /vacancies`, `POST /resumes`); здесь только чтение и расчёт,
    поэтому повторный вызов не тратит токены LLM.
    """
    try:
        vacancy = await get_vacancy(db, current_user.id, payload.vacancy_id)
        resume = await get_resume(db, current_user.id, payload.resume_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    vacancy_skills = await load_vacancy_skills(db, vacancy.id)
    resume_skills = await load_resume_skills(db, resume.id)
    profile = await get_profile(db, current_user.id)
    gaps = await compute_gaps(db, current_user.id, vacancy.id)

    return AnalysisResponse(
        vacancy=vacancy_read(vacancy, vacancy_skills),
        resume=resume_read(resume, resume_skills),
        profile=profile_read(profile),
        gaps=gap_analysis_read(gaps),
    )
