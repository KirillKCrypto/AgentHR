"""Эндпоинты профиля знаний: срез уровня и gap-анализ под вакансию."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.api.mappers import gap_analysis_read, profile_read
from app.schemas.analysis import GapAnalysisRead, ProfileRead
from app.services.profile import NotFoundError, compute_gaps, get_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def read_profile(db: DbSession, current_user: CurrentUser) -> ProfileRead:
    """Профиль знаний: освоенные темы и навыки вне онтологии."""
    snapshot = await get_profile(db, current_user.id)
    return profile_read(snapshot)


@router.get("/gaps")
async def read_gaps(
    vacancy_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> GapAnalysisRead:
    """Разрывы между требованиями вакансии и текущим профилем."""
    try:
        report = await compute_gaps(db, current_user.id, vacancy_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return gap_analysis_read(report)
