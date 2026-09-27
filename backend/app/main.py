"""Точка входа FastAPI-приложения AgentHR."""

from fastapi import FastAPI

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Проверка работоспособности сервиса."""
    return {"status": "ok", "environment": settings.environment}
