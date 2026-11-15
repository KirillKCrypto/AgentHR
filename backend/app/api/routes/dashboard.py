"""Эндпоинт сводного прогресса."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.progress import DashboardRead
from app.services.progress import build_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def read_dashboard(
    db: DbSession,
    current_user: CurrentUser,
    vacancy_id: Annotated[UUID | None, Query()] = None,
) -> DashboardRead:
    """Готовность, план, последнее интервью и история."""
    snapshot = await build_dashboard(
        db,
        current_user.id,
        vacancy_id=vacancy_id,
    )
    if vacancy_id is not None and snapshot.vacancy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вакансия не найдена",
        )
    return snapshot
