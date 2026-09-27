# PROJECT_MAP — карта репозитория AgentHR

> Навигация: [`INDEX.md`](../INDEX.md) → **PROJECT_MAP.md** (этот файл) → [`ARCHITECTURE.md`](ARCHITECTURE.md).
> Составлено по состоянию на 27.09.2026.
>
> Документ описывает **фактическое** состояние репозитория. Всё, что пока не реализовано,
> помечено «План» со ссылкой на источник — [`AGENTS.md`](../AGENTS.md).

---

## 1. Корень репозитория

| Путь | Роль | Назначение |
|---|---|---|
| `README.md` | DOCUMENTATION | краткое описание проекта, стека и структуры |
| `AGENTS.md` | DOCUMENTATION | контекст проекта, план на 8 недель, архитектурные правила |
| `INDEX.md` | DOCUMENTATION | главная точка входа для ИИ-агентов |
| `docs/` | DOCUMENTATION | навигационная документация (PROJECT_MAP, ARCHITECTURE) |
| `backend/` | APPLICATION | FastAPI-каркас (`/health`, `/health/db`, JWT-auth, модель `User`, миграции); Harness и Tools — план |
| `frontend/` | APPLICATION (План) | будущий React SPA; сейчас README-заглушка |
| `infra/` | INFRASTRUCTURE | работающая локальная БД: PostgreSQL 16 + pgvector |
| `.gitignore` | CONFIG | исключения git |
| `.editorconfig` | CONFIG | единый стиль (UTF-8, LF, отступы) |
| `.gitattributes` | CONFIG | нормализация переводов строк |

---

## 2. Полное дерево

```text
AgentHR/
├── .editorconfig
├── .gitattributes
├── .gitignore
├── AGENTS.md
├── INDEX.md
├── README.md
├── backend/
│   ├── .env.example
│   ├── .env                   (локальный, в git не попадает)
│   ├── .python-version        (пин Python 3.13)
│   ├── README.md
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py             (настройка миграций, URL из настроек)
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 6d7c8a1b787e_enable_pgvector_extension.py
│   │       └── 68cf3aa5da9d_create_users_table.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            (точка входа FastAPI; роутеры, /health, /health/db)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py        (get_current_user — Bearer)
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py    (register, login, refresh)
│   │   │       └── users.py   (/me)
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py      (настройки, pydantic-settings)
│   │   │   └── security.py    (argon2-хеши, JWT)
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py        (Base для моделей)
│   │   │   └── session.py     (async-движок, get_db)
│   │   ├── models/
│   │   │   ├── __init__.py    (импортирует все модели для Alembic)
│   │   │   └── user.py        (модель User)
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── auth.py        (Pydantic-схемы auth)
│   ├── pyproject.toml
│   ├── tests/
│   │   ├── test_health.py
│   │   ├── test_health_db.py
│   │   ├── test_user_model.py
│   │   └── test_auth.py
│   └── uv.lock                (генерируется, коммитится)
├── docs/
│   ├── ARCHITECTURE.md
│   └── PROJECT_MAP.md
├── frontend/
│   └── README.md
└── infra/
    ├── .env.example
    ├── .env              (локальный, в git не попадает)
    ├── README.md
    └── docker-compose.yml
```

---

## 3. Ответственность каталогов

### `infra/`

**Role:** INFRASTRUCTURE / DEPLOYMENT

**Назначение:** локальная инфраструктура разработки — один сервис: PostgreSQL 16 с расширением
pgvector.

**Содержит:** `docker-compose.yml`, `.env.example`, `.env` (локальный), `README.md`.

**Зависит от:** Docker Desktop; значений переменных из `infra/.env`.

**Используется:** разработчиками (команды `docker compose`); backend подключается к БД
по `localhost:${POSTGRES_PORT}` (`DATABASE_URL`).

**Важно:** данные хранятся в named volume `agenthr_postgres_data`; удаляются только
`docker compose down -v`.

### `backend/`

**Role:** APPLICATION (backend)

**Назначение:** backend-приложение AgentHR. Реализован каркас: FastAPI-точка входа
(`app/main.py`: роутеры, `/health`, `/health/db`), JWT-аутентификация (`app/api/`,
`app/core/security.py`), настройки (`app/core/config.py`), слой БД (`app/db/`), модель `User`
(`app/models/`), миграции (`alembic/`), тесты (`tests/`), зависимости через uv.

**Цель по плану:** остальные модели и схема БД, доменные REST API, Agent Harness (LangGraph),
реестр Tools, провайдер-агностичный слой LLM.
Источники: `backend/README.md`, [`AGENTS.md`](../AGENTS.md) §2–3, §6.

**Содержит сейчас:** `app/` (api, core, db, models, schemas), `alembic/`, `alembic.ini`,
`tests/`, `pyproject.toml`, `uv.lock`, `.env.example`, `.python-version`, `README.md`.
Доменных сервисов пока нет.

### `frontend/` — План

**Role:** APPLICATION (frontend)

**Цель по плану:** React + TypeScript + Vite SPA, 7 экранов, TanStack Query, shadcn/ui.
Источники: `frontend/README.md`, [`AGENTS.md`](../AGENTS.md) §7.

**Сейчас содержит:** только `README.md`. Кода нет.

### `docs/`

**Role:** DOCUMENTATION

Навигационные документы для ИИ-агентов: [`PROJECT_MAP.md`](PROJECT_MAP.md) (этот файл),
[`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 4. Ответственность файлов

### Уровень 1 — критичные

#### `AGENTS.md`

**Role:** DOCUMENTATION (контекст и правила проекта)

**Responsibility:** исходные требования, целевая архитектура, модель данных, описание
AI-агента и его Tools, граф знаний, план на 8 недель, тестирование, риски, decision log,
правила работы агента, глоссарий (§0–§14).

**Depends on:** —

**Used by:** вся документация и разработка ссылаются на него как на источник требований.

**Important:** главный источник истины по замыслу. При расхождении кода и этого файла — зафиксировать
расхождение, не «дорисовывать» план под факт.

#### `infra/docker-compose.yml`

**Role:** DEPLOYMENT

**Responsibility:** описывает единственный сервис `postgres` (проект `agenthr`):
образ `pgvector/pgvector:pg16`, контейнер `agenthr-postgres`, `restart: unless-stopped`,
переменные окружения из `.env`, порт `${POSTGRES_PORT}:5432`, volume `postgres_data`,
healthcheck (`pg_isready`, интервал 5 с, 10 попыток).

**Depends on:** `infra/.env` (подстановка переменных), Docker Desktop.

**Used by:** локальный запуск БД для всей команды; backend (подключение к БД).

**Important:** изменение порта/volume/healthcheck затрагивает `infra/.env`, `infra/README.md`
и `DATABASE_URL` в `backend/.env`. `docker compose down -v` удаляет данные.

#### `infra/.env.example`

**Role:** CONFIG (шаблон)

**Responsibility:** шаблон локального окружения: `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`, `POSTGRES_PORT`. Копируется в `infra/.env`.

**Depends on:** —

**Used by:** `docker compose` (значения для контейнера), `infra/README.md`.

**Important:** реальный `.env` не коммитится (см. `.gitignore`). Значения из файла в документации
не приводятся (кроме дефолтов шаблона, предназначенного для локальной разработки).

#### `backend/app/main.py`

**Role:** ENTRYPOINT / API

**Responsibility:** создаёт FastAPI-приложение, подключает роутеры (`auth`, `users`), объявляет
health-эндпоинты (`/health`, `/health/db` — `SELECT 1`, 503 при недоступной БД), управляет
ресурсами (lifespan: `engine.dispose()`).

**Depends on:** `backend/app/api/routes/*`, `backend/app/core/config.py`,
`backend/app/db/session.py`, `fastapi`.

**Used by:** запуск `uvicorn app.main:app`; тесты `backend/tests/`.

**Important:** при добавлении роутеров подключать их здесь; бизнес-логику в точку входа
не складывать.

#### `backend/app/core/config.py`

**Role:** CONFIG

**Responsibility:** настройки приложения (`Settings`) через pydantic-settings; читает переменные
окружения и `backend/.env`; `get_settings()` кэширует экземпляр. Переменные: `APP_NAME`,
`ENVIRONMENT`, `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`,
`REFRESH_TOKEN_EXPIRE_DAYS`.

**Depends on:** `pydantic-settings`.

**Used by:** `backend/app/main.py`, `backend/app/core/security.py`,
`backend/app/db/session.py`, `backend/alembic/env.py`.

**Important:** при добавлении переменных обновлять `backend/.env.example`; секреты в репозитории
не хранить.

#### `backend/app/core/security.py`

**Role:** SECURITY

**Responsibility:** хеширование паролей (argon2id через `pwdlib`: `hash_password`,
`verify_password`) и JWT (`create_token`, `decode_token`; claims `sub`/`type`/`iat`/`exp`;
алгоритм и TTL — из настроек).

**Depends on:** `backend/app/core/config.py`, `pwdlib`, `pyjwt`.

**Used by:** `backend/app/api/routes/auth.py`, `backend/app/api/deps.py`, тесты.

**Important:** менять формат claims/TTL осторожно — влияет на все выданные токены;
`JWT_SECRET_KEY` в продакшене — только из окружения.

#### `backend/app/db/session.py`

**Role:** DATABASE

**Responsibility:** async-движок SQLAlchemy (`asyncpg`, `pool_pre_ping`), фабрика сессий
(`async_session_factory`), зависимость FastAPI `get_db()` (сессия на запрос).

**Depends on:** `backend/app/core/config.py`, `sqlalchemy[asyncio]`, `asyncpg`.

**Used by:** `backend/app/main.py`, `backend/app/api/routes/auth.py`, `backend/app/api/deps.py`,
тесты, в будущем — роутеры и сервисы.

**Important:** единственная точка создания сессий; URL — из настроек (`DATABASE_URL`).

#### `backend/app/models/user.py`

**Role:** MODEL

**Responsibility:** ORM-модель `User`: `id` (UUID, `gen_random_uuid()`), `email` (уникальный),
`password_hash` (argon2), `created_at` (`timestamptz`, `now()`).

**Depends on:** `backend/app/db/base.py`.

**Used by:** auth (`login`, `register`, `deps.get_current_user`), Alembic (autogenerate).

**Important:** изменение модели требует новой миграции (`alembic revision --autogenerate`).

### Уровень 2 — важные

#### `README.md`

**Role:** DOCUMENTATION

**Responsibility:** краткое описание проекта, ключевая идея, сценарий, стек, структура, статус.

**Used by:** точка знакомства для людей.

#### `INDEX.md`

**Role:** DOCUMENTATION

**Responsibility:** главная точка входа для ИИ-агентов: обзор, структура, компоненты, карта
документации, критические области, правила, быстрая навигация.

**Used by:** ИИ-агенты при первом открытии репозитория.

#### `infra/README.md`

**Role:** DOCUMENTATION

**Responsibility:** практические команды для `infra/`: запуск, проверка статуса, подключение,
проверка расширения `vector`, остановка.

**Used by:** разработчики при работе с локальной БД.

#### `backend/alembic/env.py`

**Role:** MIGRATION

**Responsibility:** окружение Alembic: URL БД из настроек приложения,
`target_metadata = Base.metadata` (для autogenerate), async-запуск миграций.

**Depends on:** `backend/app/core/config.py`, `backend/app/models/__init__.py`, `alembic`.

**Used by:** команды `alembic upgrade/downgrade/revision`.

#### `backend/alembic.ini`

**Role:** CONFIG

**Responsibility:** конфигурация Alembic: расположение миграций (`alembic/`), логирование;
URL намеренно не задаётся здесь (берётся в `env.py` из настроек).

**Used by:** команды Alembic.

#### `backend/pyproject.toml`

**Role:** BUILD / CONFIG

**Responsibility:** метаданные проекта, зависимости (fastapi, uvicorn, pydantic-settings,
sqlalchemy[asyncio], asyncpg, alembic, pwdlib[argon2], pyjwt, email-validator), dev-группа
(pytest, pytest-asyncio, httpx2, ruff), конфигурация pytest (`testpaths`, `pythonpath`,
`asyncio_mode`) и ruff.

**Depends on:** —

**Used by:** uv (sync/run), разработчики.

#### `backend/app/api/deps.py`

**Role:** API (зависимости)

**Responsibility:** `get_current_user` — извлекает Bearer-токен, проверяет access-JWT, загружает
`User` из БД; при любой проблеме — 401 с заголовком `WWW-Authenticate: Bearer`.

**Depends on:** `backend/app/core/security.py`, `backend/app/db/session.py`,
`backend/app/models/`.

**Used by:** `backend/app/api/routes/users.py` (и будущие защищённые роутеры).

#### `backend/app/api/routes/auth.py`

**Role:** API

**Responsibility:** `POST /auth/register` (argon2-хеш, 409 при дубликате email),
`POST /auth/login` (проверка пароля, пара токенов, 401; фиктивный хеш выравнивает время ответа
для несуществующих email), `POST /auth/refresh` (новая пара по refresh-токену).

**Depends on:** `backend/app/core/security.py`, `backend/app/db/session.py`,
`backend/app/schemas/auth.py`.

**Used by:** подключается в `backend/app/main.py`.

#### `backend/app/api/routes/users.py`

**Role:** API

**Responsibility:** `GET /me` — текущий пользователь (требует access-токен).

**Depends on:** `backend/app/api/deps.py`, `backend/app/schemas/auth.py`.

**Used by:** подключается в `backend/app/main.py`.

#### `backend/app/schemas/auth.py`

**Role:** SCHEMA (DTO)

**Responsibility:** Pydantic-схемы: `RegisterRequest`, `LoginRequest`, `RefreshRequest`,
`TokenResponse`, `UserRead`. Пароль и `password_hash` не возвращаются ни в одной схеме.

**Depends on:** `pydantic`.

**Used by:** `backend/app/api/routes/auth.py`, `backend/app/api/routes/users.py`.

#### `backend/tests/test_health.py`

**Role:** TEST

**Responsibility:** тесты `/health` (200 + статус) и доступности `/docs` через FastAPI TestClient.

**Depends on:** `backend/app/main.py` (импортирует `app`).

**Used by:** `uv run pytest`.

#### `backend/tests/test_health_db.py`

**Role:** TEST

**Responsibility:** тесты `/health/db`: 200 при доступной БД; 503 при `SQLAlchemyError`
и при `OSError` (сервер БД недоступен). БД подменяется через `app.dependency_overrides` —
реальный Postgres тестам не нужен.

**Depends on:** `backend/app/main.py`, `backend/app/db/session.py`, `pytest`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_user_model.py`

**Role:** TEST

**Responsibility:** интеграционный тест: вставка `User` в реальную БД, чтение обратно, очистка
данных; пропускается, если PostgreSQL недоступен. Требует `pytest-asyncio`.

**Depends on:** `backend/app/models/user.py`, `backend/app/db/session.py`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_auth.py`

**Role:** TEST

**Responsibility:** интеграционные тесты auth через `httpx2.AsyncClient` + `ASGITransport`:
регистрация/дубликат/валидация, логин (успех и ошибки), `/me` (успех, отсутствие/битый/
просроченный токен, refresh вместо access), refresh. Пропускаются без БД; созданные
пользователи удаляются после тестов.

**Depends on:** `backend/app/main.py`, `backend/app/db/session.py`, `httpx2`, `pytest-asyncio`.

**Used by:** `uv run pytest`.

#### `backend/.env.example`

**Role:** CONFIG (шаблон)

**Responsibility:** шаблон локальных настроек backend: `APP_NAME`, `ENVIRONMENT`, `DATABASE_URL`,
`JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`.
Копируется в `backend/.env` (в git не попадает).

**Depends on:** —

**Used by:** pydantic-settings (чтение `backend/.env`).

### Уровень 3 — вспомогательные

| Файл | Роль | Назначение |
|---|---|---|
| `.gitignore` | CONFIG | исключения: Python-кэши, `.venv`, `node_modules`, `dist`, `.env` (кроме `.env.example`), IDE, OS |
| `.editorconfig` | CONFIG | UTF-8, LF; Python — 4 пробела, TS/JS/JSON/YAML/CSS/HTML — 2 пробела |
| `.gitattributes` | CONFIG | `* text=auto eol=lf`; CRLF для `.bat`/`.ps1` |
| `backend/README.md` | DOCUMENTATION | команды запуска, тестов, миграций; эндпоинты; состав backend |
| `backend/.python-version` | CONFIG | пин версии Python (3.13) для uv |
| `backend/app/db/base.py` | MODEL | базовый класс `Base` для ORM-моделей |
| `backend/app/models/__init__.py` | MODEL | импорт всех моделей и `Base` (нужен Alembic для autogenerate) |
| `backend/app/api/__init__.py`, `backend/app/api/routes/__init__.py`, `backend/app/schemas/__init__.py` | PACKAGE | пакеты-инициализаторы |
| `backend/alembic/versions/*` | MIGRATION | файлы миграций (генерируются, коммитятся) |
| `frontend/README.md` | DOCUMENTATION | заглушка: состав будущего frontend и стек |
| `docs/PROJECT_MAP.md` | DOCUMENTATION | этот файл |
| `docs/ARCHITECTURE.md` | DOCUMENTATION | архитектура: факт и план |

---

## 5. Зависимости между модулями

**Факт.** Зависимости кода (backend):

```text
uvicorn app.main:app
        │
        ▼
app/main.py ──▶ app/core/config.py ──▶ pydantic-settings (backend/.env)
    │   │
    │   ├──▶ app/db/session.py ──▶ create_async_engine (asyncpg) ──▶ PostgreSQL (localhost:5433)
    │   │
    │   └── /health/db ──▶ SELECT 1 через get_db
    │
    ├── app/api/routes/auth.py ──▶ app/core/security.py (argon2, JWT)
    │        │                        ▲
    │        └──▶ app/db/session.py   │
    │                                 │
    └── app/api/routes/users.py ──▶ app/api/deps.py (get_current_user)

app/models/* ──▶ Base.metadata
alembic/env.py ──▶ config (settings) + Base.metadata ──▶ миграции в БД

tests/* ──▶ app.main (TestClient / AsyncClient); /health/db — через dependency_overrides;
            test_user_model.py и test_auth.py ──▶ реальная БД (skip, если недоступна)
```

`Base.metadata` содержит модель `User`; `app/models/__init__.py` импортирует все модели,
поэтому autogenerate видит полные метаданные. Остальные таблицы
([`AGENTS.md`](../AGENTS.md) §5) — по плану недель 3–4.

Текущие инфраструктурные связи:

```text
infra/.env ──(подстановка ${...})──▶ infra/docker-compose.yml ──(запускает)──▶ контейнер agenthr-postgres
                                                                                       │
                                                                             named volume postgres_data
```

Backend подключается к БД по `localhost:${POSTGRES_PORT}` (порт на хосте, по умолчанию `5433`).

**План** ([`AGENTS.md`](../AGENTS.md) §2): `Frontend → Backend API → Agent Harness → Tools →
БД / граф знаний / vector store`. Прямой доступ LLM к данным запрещён — только через Tools (§2.3).
Подробная схема — в [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 6. Точки входа

| Точка входа | Файл | Статус |
|---|---|---|
| Запуск инфраструктуры | `infra/docker-compose.yml` | реализовано |
| Backend-приложение | `backend/app/main.py` (uvicorn) | каркас + auth реализованы |
| Миграции БД | `backend/alembic/` (`uv run alembic ...`) | 2 миграции: pgvector, users |
| Прогон тестов backend | `backend/tests/` (pytest) | 20 тестов |
| Frontend-приложение | — | нет (план: `frontend/`) |

---

## 7. Конфигурационные файлы

### `infra/.env.example` (и локальный `infra/.env`)

| Переменная | Назначение | Секрет |
|---|---|---|
| `POSTGRES_USER` | логин суперпользователя контейнера | да |
| `POSTGRES_PASSWORD` | пароль | да |
| `POSTGRES_DB` | имя базы, создаваемой при инициализации | нет |
| `POSTGRES_PORT` | порт БД на хосте (по умолчанию `5433`; 5432 часто занят локальным PostgreSQL) | нет |

### `backend/.env.example` (и локальный `backend/.env`)

| Переменная | Назначение | Секрет |
|---|---|---|
| `APP_NAME` | заголовок FastAPI-приложения | нет |
| `ENVIRONMENT` | название окружения (`local`, ...) | нет |
| `DATABASE_URL` | строка подключения (`postgresql+asyncpg://...@localhost:5433/agenthr`) | да (содержит пароль) |
| `JWT_SECRET_KEY` | секрет подписи JWT (код содержит dev-дефолт; в проде — только из окружения) | да |
| `JWT_ALGORITHM` | алгоритм подписи (`HS256`) | нет |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | время жизни access-токена (по умолчанию 30) | нет |
| `REFRESH_TOKEN_EXPIRE_DAYS` | время жизни refresh-токена (по умолчанию 30) | нет |

### `backend/pyproject.toml` и `backend/alembic.ini`

- `pyproject.toml` — зависимости, dev-группа, конфигурация pytest и ruff.
- `alembic.ini` — расположение миграций и логирование; URL БД задаётся в `alembic/env.py`.

### Прочие конфигурационные файлы

- `.editorconfig` — единый стиль форматирования.
- `.gitattributes` — нормализация переводов строк.
- `.gitignore` — исключения git.
- `backend/.python-version` — пин Python 3.13 для uv.

### Отсутствуют (План)

`package.json` (frontend), `Dockerfile` приложений, CI-конфигурация — появятся вместе с кодом.

---

## 8. Компоненты БД

**Факт:**

- СУБД: PostgreSQL 16 в контейнере `agenthr-postgres` (образ `pgvector/pgvector:pg16`).
- Расширение `vector` создаётся миграцией `6d7c8a1b787e` (`CREATE EXTENSION IF NOT EXISTS vector`);
  откат миграции удаляет расширение.
- Подключение backend: `DATABASE_URL` из `backend/.env` (дефолт в коде —
  `postgresql+asyncpg://...@localhost:5433/agenthr`); движок — `backend/app/db/session.py`.
- Health-проверка: `GET /health/db` выполняет `SELECT 1`; 200 — доступна, 503 — недоступна.
- Миграции: Alembic (async), `backend/alembic/`; состояние — `alembic current`.
  Ревизии: `6d7c8a1b787e` (pgvector) → `68cf3aa5da9d` (таблица `users`); цикл
  `upgrade head` → `downgrade -1` → `upgrade head` проверен.
- Модель `User` (`backend/app/models/user.py`): `id` (UUID, `gen_random_uuid()`), `email`
  (уникальный), `password_hash` (argon2id-хеш), `created_at` (`timestamptz`, `now()`).
- Таблица `users` используется auth-эндпоинтами; plaintext-пароли не хранятся нигде.

**План** ([`AGENTS.md`](../AGENTS.md) §4–5):

- Остальные таблицы схемы: `resumes`, `vacancies`, `topics`, `topic_prerequisites`,
  `user_skill_states`, `interview_sessions` / `interview_turns`, `agent_actions`,
  `learning_plans` / `plan_items`, `embeddings` (pgvector).
- ORM-модели (SQLAlchemy 2) — от `Base` в `backend/app/db/base.py`; миграции — autogenerate.
- Граф знаний на MVP — реляционная модель в Postgres, доступ через репозиторий-границу.

---

## 9. Внешние интеграции

**Реализованных нет.**

**План** ([`AGENTS.md`](../AGENTS.md) §6): LLM-провайдер — OpenAI (запасной вариант — Anthropic)
через провайдер-агностичный слой; function-calling + структурный JSON. Расположение в коде
появится в `backend/`.

---

## 10. Тесты

**Факт:** `backend/tests/` — 20 тестов на pytest (+ `pytest-asyncio`):

- `test_health.py` — `/health` (200 + статус) и `/docs` (200);
- `test_health_db.py` — `/health/db`: 200 и 503 (два случая: `SQLAlchemyError`, `OSError`)
  через подмену зависимости `get_db`; реальная БД не требуется;
- `test_user_model.py` — интеграционный: вставка/чтение `User` в реальной БД, очистка данных;
  пропускается, если PostgreSQL недоступен;
- `test_auth.py` — интеграционные тесты auth (register/login/me/refresh + негативные кейсы)
  через `httpx2.AsyncClient` + `ASGITransport`; созданные пользователи удаляются.

Запуск: `uv run pytest` из `backend/`. Конфигурация — в `backend/pyproject.toml`
(`testpaths`, `pythonpath`, `asyncio_mode`).

**План** ([`AGENTS.md`](../AGENTS.md) §9): функциональные тесты, агентские (на мок-LLM),
сценарные e2e, тесты адаптивности, eval-наборы качества LLM.

---

## 11. Скрипты

Нет ни каталога `scripts/`, ни `Makefile`, ни npm-скриптов. Все существующие операции — команды
из [`infra/README.md`](../infra/README.md) (`docker compose`) и
[`backend/README.md`](../backend/README.md) (`uv sync`, `uv run uvicorn`, `uv run pytest`,
`uv run ruff`, `uv run alembic upgrade head` и др.).

---

## 12. Генерируемые файлы

- `backend/uv.lock` — генерируется uv; коммитится; вручную не редактируется.
- `backend/alembic/versions/*` — файлы миграций (генерация `alembic revision`); коммитятся;
  применённые ревизии вручную не редактируются.
- Локальные/игнорируемые: `backend/.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`,
  `node_modules/`, `dist/`, `*.log` — перечислены в `.gitignore`.
- `infra/.env` и `backend/.env` — локальные файлы (копии `.env.example`), в git не попадают.
