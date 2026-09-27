"""Эндпоинты пользователя."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models import User
from app.schemas.auth import UserRead

router = APIRouter(tags=["users"])


@router.get("/me")
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    """Возвращает текущего пользователя."""
    return UserRead.model_validate(current_user)
