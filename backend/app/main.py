"""Точка входа FastAPI-приложения AgentHR."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.analysis import router as analysis_router
from app.api.routes.auth import router as auth_router
from app.api.routes.profile import router as profile_router
from app.api.routes.resumes import router as resumes_router
from app.api.routes.users import router as users_router
from app.api.routes.vacancies import router as vacancies_router
from app.core.config import get_settings
from app.db.session import engine, get_db
from app.llm.base import LLMError

logger = logging.getLogger(__name__)

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
app.include_router(vacancies_router)
app.include_router(resumes_router)
app.include_router(profile_router)
app.include_router(analysis_router)


@app.exception_handler(LLMError)
async def llm_error_handler(_: Request, exc: LLMError) -> JSONResponse:
    """Ошибка модели — 502 с понятным текстом; причина уходит в лог."""
    logger.warning("Ошибка LLM: %s", exc)
    return JSONResponse(
        status_code=502,
        content={"detail": "LLM недоступна — попробуйте позже"},
    )


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
