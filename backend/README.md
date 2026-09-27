# Backend

Backend-приложение AgentHR на FastAPI. Реализован каркас: точка входа, health-эндпоинты,
настройки, подключение к БД и миграции.

Стек: Python 3.13, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, LangGraph (план).

## Запуск

```powershell
uv sync
Copy-Item .env.example .env              # один раз, локальные настройки не коммитятся
uv run alembic upgrade head              # применить миграции (нужна запущенная БД из infra/)
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000, документация — /docs
```

## Тесты и линтер

```powershell
uv run pytest
uv run ruff check .
```

## Миграции

```powershell
uv run alembic upgrade head                        # применить все миграции
uv run alembic current                             # текущая ревизия
uv run alembic downgrade base                      # откатить всё
uv run alembic revision --autogenerate -m "..."    # новая миграция по моделям
```

URL БД берётся из настроек (`backend/.env`, переменная `DATABASE_URL`); в коде есть локальный
дефолт. Применённые миграции вручную не редактируются.

## Структура

- `app/main.py` — точка входа FastAPI: `/health`, `/health/db`
- `app/core/config.py` — настройки (pydantic-settings, читает `.env`)
- `app/db/session.py` — async-движок, фабрика сессий, зависимость `get_db`
- `app/db/base.py` — базовый класс моделей (`Base`) для будущих таблиц
- `alembic/` — миграции (async), `alembic/versions/`
- `tests/` — тесты (pytest + FastAPI TestClient)

Дальше по плану (см. `AGENTS.md`): модели и начальная схема БД, REST API, Agent Harness,
реестр Tools, JWT-auth, слой LLM.
