# Backend

Backend-приложение AgentHR на FastAPI. Реализован скелет: точка входа, `/health`, настройки,
тесты.

Стек: Python 3.13, FastAPI, SQLAlchemy 2 (async), Alembic, LangGraph (план).

## Запуск

```powershell
uv sync
Copy-Item .env.example .env              # один раз, локальные настройки не коммитятся
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000, документация — /docs
```

## Тесты и линтер

```powershell
uv run pytest
uv run ruff check .
```

## Структура

- `app/main.py` — точка входа FastAPI, эндпоинт `/health`
- `app/core/config.py` — настройки (pydantic-settings, читает `.env`)
- `tests/` — тесты (pytest + FastAPI TestClient)
- `pyproject.toml` — зависимости и конфигурация инструментов (uv)

Дальше по плану (см. `AGENTS.md`): REST API, Agent Harness, реестр Tools, слой БД
(SQLAlchemy + Alembic), JWT-auth, слой LLM.
