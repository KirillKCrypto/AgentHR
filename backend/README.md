# Backend

Backend-приложение AgentHR на FastAPI. Реализованы: каркас, health-эндпоинты,
JWT-аутентификация, слой LLM (mock/OpenAI), подключение к БД, модель User и миграции.

Стек: Python 3.13, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, PyJWT, pwdlib (argon2),
openai, LangGraph (план).

## Запуск

```powershell
uv sync
Copy-Item .env.example .env              # один раз, локальные настройки не коммитятся
uv run alembic upgrade head              # применить миграции (нужна запущенная БД из infra/)
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000, документация — /docs
```

## Эндпоинты

- `GET /health`, `GET /health/db` — проверки работоспособности;
- `POST /auth/register` — регистрация `{email, password}` → 201 (409, если email занят);
- `POST /auth/login` — вход `{email, password}` → `{access_token, refresh_token, token_type}`;
- `POST /auth/refresh` — обновление пары токенов `{refresh_token}`;
- `GET /me` — текущий пользователь (заголовок `Authorization: Bearer <access_token>`).

## LLM

- По умолчанию `LLM_PROVIDER=mock` — детерминированный провайдер для тестов, сеть не нужна.
- Для реальных вызовов: `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL` в `backend/.env`.
- Интерфейс (`app/llm/base.py`): `generate_with_tools` (function calling) и
  `generate_structured` (структурированный JSON по схеме).

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

- `app/main.py` — точка входа FastAPI: роутеры, `/health`, `/health/db`
- `app/api/` — роутеры (`routes/auth.py`, `routes/users.py`) и зависимости (`deps.py`)
- `app/core/config.py` — настройки (pydantic-settings, читает `.env`)
- `app/core/security.py` — argon2-хеши паролей, выпуск/проверка JWT
- `app/db/session.py` — async-движок, фабрика сессий, зависимость `get_db`
- `app/db/base.py` — базовый класс моделей (`Base`)
- `app/llm/` — слой LLM: `base.py` (интерфейс), `mock.py`, `openai.py`, `factory.py`
- `app/models/` — ORM-модели (сейчас `User` в `user.py`)
- `app/schemas/` — Pydantic-схемы (сейчас `auth.py`)
- `alembic/` — миграции (async), `alembic/versions/`
- `tests/` — тесты (pytest + httpx2, интеграционные требуют запущенную БД)

## Безопасность (важно)

`JWT_SECRET_KEY` в коде — только dev-дефолт; в продакшене обязательно задавать через окружение.
Refresh-токены stateless: отзыв до истечения не поддерживается (осознанный компромисс MVP).
Ключ `OPENAI_API_KEY` — только через окружение.

Дальше по плану (см. `AGENTS.md`): остальные модели и таблицы, доменные REST API, Agent Harness,
реестр Tools.
