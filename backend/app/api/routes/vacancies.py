"""Эндпоинты вакансий: загрузка текста, список и карточка."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, Embedder, LlmProvider
from app.api.mappers import vacancy_read
from app.models import Vacancy
from app.schemas.analysis import VacancyCreate, VacancyRead, VacancySummary
from app.services.analysis import AnalysisError
from app.services.profile import NotFoundError, analyze_vacancy, get_vacancy, load_vacancy_skills

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_vacancy(
    payload: VacancyCreate,
    db: DbSession,
    provider: LlmProvider,
    embedder: Embedder,
    current_user: CurrentUser,
) -> VacancyRead:
    """Создаёт вакансию и сразу извлекает из неё требования."""
    try:
        vacancy = await analyze_vacancy(
            db,
            provider,
            current_user.id,
            raw_text=payload.raw_text,
            title=payload.title,
            company=payload.company,
            embedder=embedder,
        )
    except AnalysisError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    skills = await load_vacancy_skills(db, vacancy.id)
    return vacancy_read(vacancy, skills)


@router.get("")
async def list_vacancies(
    db: DbSession,
    current_user: CurrentUser,
) -> list[VacancySummary]:
    """Вакансии текущего пользователя (без навыков — для дашборда)."""
    vacancies = (
        await db.scalars(
            select(Vacancy)
            .where(Vacancy.user_id == current_user.id)
            .order_by(Vacancy.created_at.desc())
        )
    ).all()
    return [VacancySummary.model_validate(vacancy) for vacancy in vacancies]


@router.get("/{vacancy_id}")
async def read_vacancy(
    vacancy_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> VacancyRead:
    """Карточка вакансии с извлечёнными навыками."""
    try:
        vacancy = await get_vacancy(db, current_user.id, vacancy_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    skills = await load_vacancy_skills(db, vacancy.id)
    return vacancy_read(vacancy, skills)
