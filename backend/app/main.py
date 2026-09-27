"""Точка входа FastAPI-приложения AgentHR."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.core.config import get_settings
from app.db.session import engine, get_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Освобождает ресурсы при остановке приложения."""
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Проверка работоспособности сервиса."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/db", tags=["system"])
async def health_db(db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, str]:
    """Проверка доступности БД (SELECT 1)."""
    try:
        await db.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as exc:
        # OSError — ошибка соединения (сервер БД недоступен), SQLAlchemyError — ошибка запроса
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "database": "ok"}
