"""Эндпоинты планов подготовки."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.api.mappers import plan_read, plan_summary_read
from app.schemas.plan import PlanCreate, PlanRead, PlanSummaryRead
from app.services.plans import (
    PlanError,
    PlanNotFoundError,
    create_plan,
    get_plan,
    list_plans,
)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_learning_plan(
    payload: PlanCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PlanRead:
    """Строит план из самых сильных тем резюме."""
    try:
        plan = await create_plan(db, current_user.id, vacancy_id=payload.vacancy_id)
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PlanError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return plan_read(plan)


@router.get("")
async def read_plans(db: DbSession, current_user: CurrentUser) -> list[PlanSummaryRead]:
    """Список планов пользователя."""
    return [plan_summary_read(plan) for plan in await list_plans(db, current_user.id)]


@router.get("/{plan_id}")
async def read_plan(
    plan_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> PlanRead:
    """План подготовки с темами."""
    try:
        plan = await get_plan(db, current_user.id, plan_id)
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return plan_read(plan)
