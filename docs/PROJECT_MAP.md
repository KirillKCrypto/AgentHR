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
| `backend/` | APPLICATION | FastAPI-каркас (`/health`, `/health/db`, JWT-auth, слой LLM, агентский слой, миграции); Harness-граф — в работе |
| `frontend/` | APPLICATION | SPA-каркас: Vite + React 19 + TS, Tailwind 4, shadcn/ui; вход/регистрация через API |
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
│   │       ├── 22cd6bbf10ed_create_agent_actions_table.py
│   │       └── 68cf3aa5da9d_create_users_table.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            (точка входа FastAPI; CORS, роутеры, /health, /health/db)
│   │   ├── agent/
│   │   │   ├── __init__.py    (реэкспорт реестра, исполнителя, аудита, harness)
│   │   │   ├── audit.py       (AgentActionRecord, AuditLogger, InMemory/Db)
│   │   │   ├── executor.py    (ToolExecutor: валидация, таймаут, аудит)
│   │   │   ├── harness.py     (AgentHarness: граф LangGraph, лимиты, checkpointer)
│   │   │   └── tools.py       (ToolDefinition, ToolRegistry, JSON Schema)
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
│   │   ├── llm/
│   │   │   ├── __init__.py    (реэкспорт интерфейса и реализаций)
│   │   │   ├── base.py        (типы и Protocol LLMProvider)
│   │   │   ├── factory.py     (выбор провайдера по настройкам)
│   │   │   ├── mock.py        (MockProvider для тестов)
│   │   │   └── openai.py      (OpenAIProvider, SDK openai)
│   │   ├── models/
│   │   │   ├── __init__.py    (импортирует все модели для Alembic)
│   │   │   ├── agent_action.py (модель AgentAction)
│   │   │   └── user.py        (модель User)
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── auth.py        (Pydantic-схемы auth)
│   ├── pyproject.toml
│   ├── tests/
│   │   ├── test_health.py
│   │   ├── test_health_db.py
│   │   ├── test_user_model.py
│   │   ├── test_auth.py
│   │   ├── test_cors.py
│   │   ├── test_llm.py
│   │   ├── test_agent_tools.py
│   │   ├── test_agent_harness.py
│   │   └── test_agent_audit.py
│   └── uv.lock                (генерируется, коммитится)
├── docs/
│   ├── ARCHITECTURE.md
│   └── PROJECT_MAP.md
├── frontend/
│   ├── .env.example           (VITE_API_BASE_URL)
│   ├── .gitignore             (node_modules, dist, локальные файлы)
│   ├── .npmrc                 (save-exact=true)
│   ├── .oxlintrc.json         (конфигурация линтера)
│   ├── README.md              (команды и соглашения)
│   ├── components.json        (конфигурация shadcn/ui)
│   ├── index.html
│   ├── package.json           (зависимости, зафиксированные версии; скрипты)
│   ├── package-lock.json      (генерируется, коммитится)
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts         (React + Tailwind 4, алиас @/*)
│   ├── public/
│   │   └── favicon.svg
│   └── src/
│       ├── main.tsx           (QueryClientProvider + BrowserRouter)
│       ├── App.tsx            (шапка и маршруты /, /login, 404)
│       ├── index.css          (Tailwind 4 + тема shadcn)
│       ├── api/
│       │   ├── client.ts      (fetch-обёртка, типизированные login/register/me)
│       │   └── schema.d.ts    (типы из OpenAPI, генерируется)
│       ├── components/ui/     (Button, Card, Input, Label — shadcn/ui)
│       ├── lib/
│       │   ├── tokens.ts      (сохранение/очистка токенов)
│       │   └── utils.ts       (cn)
│       └── pages/
│           ├── DashboardPage.tsx (статус сессии, /me, выход)
│           ├── LoginPage.tsx     (вход/регистрация через API)
│           └── NotFoundPage.tsx
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
(`app/main.py`: CORS, роутеры, `/health`, `/health/db`), JWT-аутентификация (`app/api/`,
`app/core/security.py`), слой LLM (`app/llm/`: интерфейс, mock- и OpenAI-провайдеры), агентский
слой (`app/agent/`: реестр Tools, исполнитель tool-calls, аудит-логгер, граф LangGraph), настройки
(`app/core/config.py`), слой БД (`app/db/`), модели `User` и `AgentAction` (`app/models/`),
миграции (`alembic/`), тесты (`tests/`), зависимости через uv.

**Цель по плану:** остальные модели и схема БД, доменные REST API, Agent Harness (LangGraph),
реестр Tools.
Источники: `backend/README.md`, [`AGENTS.md`](../AGENTS.md) §2–3, §6.

**Содержит сейчас:** `app/` (agent, api, core, db, llm, models, schemas), `alembic/`, `alembic.ini`,
`tests/`, `pyproject.toml`, `uv.lock`, `.env.example`, `.python-version`, `README.md`.
Доменных сервисов пока нет.

### `frontend/`

**Role:** APPLICATION (frontend)

**Назначение:** React SPA AgentHR. Реализован каркас с рабочим входом: Vite + React 19 +
TypeScript, Tailwind CSS 4, shadcn/ui (Base UI), роутинг (react-router 8), TanStack Query;
типизированный API-клиент (`src/api/client.ts`, типы из OpenAPI в `src/api/schema.d.ts`);
экран `/login` (регистрация и вход, состояния loading/error, токены в `src/lib/tokens.ts`,
редирект); дашборд (загрузка `/me`, выход); 404.

**Цель по плану:** остальные экраны продукта — `/vacancies/new`, `/profile`, `/plans/:id`,
`/interview/:id`, `/reports/:id` ([`AGENTS.md`](../AGENTS.md) §7).
Источник: `frontend/README.md`.

**Содержит сейчас:** `src/` (main, App, api, pages, components/ui, lib), конфигурации
(`package.json`, `vite.config.ts`, `tsconfig*.json`, `components.json`, `.npmrc`,
`.oxlintrc.json`, `.env.example`), `index.html`, `README.md`.

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

**Responsibility:** создаёт FastAPI-приложение, настраивает CORS (для frontend dev-сервера),
подключает роутеры (`auth`, `users`), объявляет health-эндпоинты (`/health`, `/health/db` —
`SELECT 1`, 503 при недоступной БД), управляет ресурсами (lifespan: `engine.dispose()`).

**Depends on:** `backend/app/api/routes/*`, `backend/app/core/config.py`,
`backend/app/db/session.py`, `fastapi`.

**Used by:** запуск `uvicorn app.main:app`; тесты `backend/tests/`.

**Important:** при добавлении роутеров подключать их здесь; бизнес-логику в точку входа
не складывать.

#### `backend/app/core/config.py`

**Role:** CONFIG

**Responsibility:** настройки приложения (`Settings`) через pydantic-settings; читает переменные
окружения и `backend/.env`; `get_settings()` кэширует экземпляр. Переменные: `APP_NAME`,
`ENVIRONMENT`, `DATABASE_URL`, `JWT_*`, `ACCESS_TOKEN_EXPIRE_MINUTES`,
`REFRESH_TOKEN_EXPIRE_DAYS`, `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `CORS_ORIGINS`.

**Depends on:** `pydantic-settings`.

**Used by:** `backend/app/main.py`, `backend/app/core/security.py`,
`backend/app/db/session.py`, `backend/app/llm/factory.py`, `backend/alembic/env.py`.

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

#### `backend/app/llm/base.py`

**Role:** LLM (интерфейс)

**Responsibility:** провайдер-агностичные типы (`ChatMessage`, `ToolSpec`, `ToolCall`,
`LLMResponse`, `StructuredResult`, `LLMUsage`, ошибки `LLMError`/`LLMConfigurationError`)
и Protocol `LLMProvider` (`generate_with_tools`, `generate_structured`, `close`).

**Depends on:** — (только стандартная библиотека).

**Used by:** `backend/app/llm/mock.py`, `backend/app/llm/openai.py`,
`backend/app/llm/factory.py`; в будущем — Agent Harness.

**Important:** изменение контракта затронет всех провайдеров и будущий Harness.

#### `backend/app/agent/tools.py`

**Role:** AGENT (реестр инструментов)

**Responsibility:** `ToolDefinition` (описание + async-обработчик), `ToolRegistry`
(регистрация, поиск, `specs()` для LLM, валидация аргументов по JSON Schema через `jsonschema`),
ошибки `ToolNotFoundError`/`ToolArgumentsError`.

**Depends on:** `backend/app/llm/base.py` (`ToolSpec`), `jsonschema`.

**Used by:** `backend/app/agent/executor.py`; в будущем — Harness и конкретные инструменты.

**Important:** каждый инструмент обязан иметь JSON Schema; повторная регистрация имени запрещена.

#### `backend/app/agent/harness.py`

**Role:** AGENT (оркестратор)

**Responsibility:** `AgentHarness` — граф LangGraph «модель → tools → модель»: лимиты
(`max_steps`, `token_budget`, `timeout_seconds`), checkpointer (`InMemorySaver`, `thread_id`),
аудит LLM-шагов и вызовов инструментов; `AgentRunResult` (статус, сообщения, токены, шаги).

**Depends on:** `app/agent/tools.py`, `app/agent/executor.py`, `app/agent/audit.py`,
`app/llm/base.py`, `langgraph`.

**Used by:** будущие агентские сценарии (M2+); тесты `backend/tests/test_agent_harness.py`.

**Important:** конфигурация лимитов — `AGENT_*` в настройках; checkpointer в памяти (рестарт
процесса теряет состояние потока).

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
sqlalchemy[asyncio], asyncpg, alembic, pwdlib[argon2], pyjwt, email-validator, openai),
dev-группа (pytest, pytest-asyncio, httpx2, ruff), конфигурация pytest (`testpaths`,
`pythonpath`, `asyncio_mode`) и ruff.

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

**Used by:** подключается в `backend/app/main.py`; вызывается frontend (`src/api/client.ts`).

#### `backend/app/api/routes/users.py`

**Role:** API

**Responsibility:** `GET /me` — текущий пользователь (требует access-токен).

**Depends on:** `backend/app/api/deps.py`, `backend/app/schemas/auth.py`.

**Used by:** подключается в `backend/app/main.py`; вызывается frontend (дашборд).

#### `backend/app/schemas/auth.py`

**Role:** SCHEMA (DTO)

**Responsibility:** Pydantic-схемы: `RegisterRequest`, `LoginRequest`, `RefreshRequest`,
`TokenResponse`, `UserRead`. Пароль и `password_hash` не возвращаются ни в одной схеме.

**Depends on:** `pydantic`.

**Used by:** `backend/app/api/routes/auth.py`, `backend/app/api/routes/users.py`; типы попадают
в OpenAPI и генерируются во фронтенд.

#### `backend/app/llm/mock.py`

**Role:** LLM (тестовая реализация)

**Responsibility:** `MockProvider` — отдаёт заранее заданные ответы по порядку и записывает
вызовы (`MockCall`); работает без сети.

**Depends on:** `backend/app/llm/base.py`.

**Used by:** тесты `backend/tests/test_llm.py`; в будущем — тесты Harness на мок-LLM.

#### `backend/app/llm/openai.py`

**Role:** LLM (интеграция)

**Responsibility:** `OpenAIProvider` на официальном SDK (`AsyncOpenAI`): function calling
(`generate_with_tools`), структурированный вывод по JSON Schema (`generate_structured`,
`response_format: json_schema`, `strict`), конвертация сообщений и usage.

**Depends on:** `openai`, `backend/app/llm/base.py`.

**Used by:** `backend/app/llm/factory.py`.

**Important:** секреты — только из настроек; живой вызов проверяется тестом со `skipif`
без ключа.

#### `backend/app/llm/factory.py`

**Role:** LLM (конфигурация)

**Responsibility:** `create_llm_provider(settings)` — выбор провайдера по `LLM_PROVIDER`
(`mock` по умолчанию; `openai` требует `OPENAI_API_KEY` и `OPENAI_MODEL`).

**Depends on:** `backend/app/core/config.py`, `backend/app/llm/*`.

**Used by:** точки сборки приложения/скриптов (в `main.py` пока не подключён).

#### `backend/app/agent/executor.py`

**Role:** AGENT (исполнение tool-calls)

**Responsibility:** `ToolExecutor` — валидирует аргументы, вызывает обработчик с таймаутом
(`asyncio.wait_for`), перехватывает ошибки (агент получает текст ошибки, цикл не падает),
пишет запись в аудит-лог; возвращает `ToolExecutionResult` для контекста LLM.

**Depends on:** `backend/app/agent/tools.py`, `backend/app/agent/audit.py`, `backend/app/llm/base.py`.

**Used by:** в будущем — Harness; тесты `backend/tests/test_agent_tools.py`.

#### `backend/app/agent/audit.py`

**Role:** AGENT (аудит)

**Responsibility:** `AgentActionRecord`, Protocol `AuditLogger`, реализации:
`InMemoryAuditLogger` (тесты без БД) и `DbAuditLogger` (запись в таблицу `agent_actions`).

**Depends on:** `backend/app/models/agent_action.py`.

**Used by:** `backend/app/agent/executor.py`; в будущем — Harness.

#### `backend/app/models/agent_action.py`

**Role:** MODEL

**Responsibility:** ORM-модель `AgentAction` (таблица `agent_actions`): шаг, tool, аргументы,
результат, статус, токены, длительность, время; `session_id` — свободная ссылка без FK
(сессии появятся на неделе 5).

**Depends on:** `backend/app/db/base.py`.

**Used by:** `backend/app/agent/audit.py`, Alembic (autogenerate).

**Important:** изменение модели требует новой миграции.

#### `frontend/src/api/client.ts`

**Role:** API-клиент (frontend)

**Responsibility:** единая точка HTTP-запросов к backend: базовый URL из `VITE_API_BASE_URL`,
заголовок `Authorization: Bearer`, ошибки `ApiError` со статусом, типизированные функции
`login`, `register`, `fetchMe` (типы — из OpenAPI).

**Depends on:** `frontend/src/api/schema.d.ts` (типы), backend API.

**Used by:** `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/DashboardPage.tsx`.

**Important:** новые вызовы API добавлять сюда; при изменении API обновлять типы
(`npm run generate:api`).

#### `frontend/src/pages/LoginPage.tsx`

**Role:** UI (экран)

**Responsibility:** вход и регистрация: переключение режимов, отправка формы, состояния
`submitting/error`, сохранение токенов, редирект на дашборд.

**Depends on:** `frontend/src/api/client.ts`, `frontend/src/lib/tokens.ts`, shadcn/ui.

**Used by:** маршрут `/login` в `frontend/src/App.tsx`.

#### `frontend/src/pages/DashboardPage.tsx`

**Role:** UI (экран)

**Responsibility:** показывает состояние сессии: нет токена / загрузка `/me` (TanStack Query) /
ошибка (401 — очистка токенов) / профиль пользователя с кнопкой «Выйти».

**Depends on:** `frontend/src/api/client.ts`, `frontend/src/lib/tokens.ts`, shadcn/ui.

**Used by:** маршрут `/` в `frontend/src/App.tsx`.

#### `frontend/src/lib/tokens.ts`

**Role:** STATE (клиентское хранилище)

**Responsibility:** сохранение, чтение и очистка access/refresh-токенов в `localStorage`.

**Used by:** `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/DashboardPage.tsx`.

**Important:** токены в `localStorage` — принятый для MVP компромисс (XSS-риск); refresh-механика
в UI пока не используется.

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

#### `backend/tests/test_cors.py`

**Role:** TEST

**Responsibility:** CORS: ответ содержит `access-control-allow-origin` для origin frontend;
preflight `OPTIONS /auth/login` разрешён.

**Depends on:** `backend/app/main.py`, `pytest`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_llm.py`

**Role:** TEST

**Responsibility:** тесты слоя LLM без сети (MockProvider: tool calls, structured, ошибки;
фабрика: mock по умолчанию, требования к openai-конфигурации) + живой тест OpenAI
со `skipif` без `OPENAI_API_KEY`/`OPENAI_MODEL`.

**Depends on:** `backend/app/llm/*`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_agent_tools.py`

**Role:** TEST

**Responsibility:** тесты реестра и исполнителя без БД: дубликаты имён, `specs()`, валидация
аргументов, успешное исполнение с аудит-записью, невалидные аргументы без вызова обработчика,
ошибка обработчика, таймаут.

**Depends on:** `backend/app/agent/*`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_agent_harness.py`

**Role:** TEST

**Responsibility:** тесты графа на мок-LLM: полный цикл с инструментом и аудитом, лимит шагов,
бюджет токенов, таймаут, ошибка LLM, ошибка инструмента (возврат в модель), продолжение
истории по `thread_id` (checkpoint).

**Depends on:** `backend/app/agent/harness.py`, `app/llm` (MockProvider).

**Used by:** `uv run pytest`.

#### `backend/tests/test_agent_audit.py`

**Role:** TEST

**Responsibility:** интеграционный тест `DbAuditLogger`: запись и чтение строки
из `agent_actions` в реальной БД; пропускается без PostgreSQL.

**Depends on:** `backend/app/agent/audit.py`, `backend/app/db/session.py`.

**Used by:** `uv run pytest`.

#### `backend/.env.example`

**Role:** CONFIG (шаблон)

**Responsibility:** шаблон локальных настроек backend: `APP_NAME`, `ENVIRONMENT`, `DATABASE_URL`,
`JWT_*`, `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `CORS_ORIGINS`. Копируется
в `backend/.env` (в git не попадает).

**Depends on:** —

**Used by:** pydantic-settings (чтение `backend/.env`).

#### `frontend/src/App.tsx`

**Role:** UI (маршрутизация)

**Responsibility:** шапка (`AgentHR`, ссылка «Вход») и маршруты: `/` → `DashboardPage`,
`/login` → `LoginPage`, `*` → `NotFoundPage`.

**Depends on:** `react-router`, `frontend/src/pages/*`.

**Used by:** `frontend/src/main.tsx`.

**Important:** новые экраны добавлять здесь; список экранов — [`AGENTS.md`](../AGENTS.md) §7.

#### `frontend/package.json`

**Role:** BUILD / CONFIG

**Responsibility:** зависимости frontend (React 19, react-router 8, TanStack Query 5,
Tailwind 4, shadcn/ui: Base UI, lucide, cn, cva), скрипты `dev` / `build` / `lint` / `preview` /
`generate:api`. Версии зафиксированы (`.npmrc` → `save-exact=true`).

**Depends on:** —

**Used by:** npm; сборка — `tsc -b && vite build`; генерация типов — `npm run generate:api`.

#### `frontend/.env.example`

**Role:** CONFIG (шаблон)

**Responsibility:** `VITE_API_BASE_URL` — базовый URL backend (по умолчанию
`http://127.0.0.1:8000`). Копируется в `frontend/.env` при необходимости.

**Used by:** `frontend/src/api/client.ts`.

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
| `backend/app/llm/__init__.py` | LLM | реэкспорт интерфейса и реализаций слоя LLM |
| `backend/app/api/__init__.py`, `backend/app/api/routes/__init__.py`, `backend/app/schemas/__init__.py` | PACKAGE | пакеты-инициализаторы |
| `backend/alembic/versions/*` | MIGRATION | файлы миграций (генерируются, коммитятся) |
| `frontend/README.md` | DOCUMENTATION | команды и соглашения frontend |
| `frontend/src/main.tsx` | UI | точка входа SPA (QueryClientProvider + BrowserRouter) |
| `frontend/src/pages/NotFoundPage.tsx` | UI | страница 404 |
| `frontend/src/api/schema.d.ts` | GENERATED | типы из OpenAPI (генерируются, не править вручную) |
| `frontend/src/components/ui/*` | UI | сгенерированные компоненты shadcn/ui |
| `frontend/src/index.css` | UI | Tailwind 4 + тема shadcn (сгенерирована) |
| `frontend/vite.config.ts`, `frontend/tsconfig*.json` | BUILD | конфигурация сборки и TS (алиас `@/*`) |
| `frontend/components.json` | CONFIG | конфигурация shadcn/ui |
| `frontend/.npmrc`, `frontend/.oxlintrc.json` | CONFIG | точные версии зависимостей; настройки линтера |
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
    ├── app/api/routes/users.py ──▶ app/api/deps.py (get_current_user)
    │
    └── (пока не подключён) app/llm/factory.py ──▶ MockProvider / OpenAIProvider (SDK openai)

app/agent/executor.py ──▶ app/agent/tools.py (JSON Schema) + app/agent/audit.py ──▶ agent_actions
app/agent/harness.py ──▶ LangGraph (граф, InMemorySaver) ──▶ LLMProvider + ToolExecutor

app/models/* ──▶ Base.metadata
alembic/env.py ──▶ config (settings) + Base.metadata ──▶ миграции в БД

tests/* ──▶ app.main (TestClient / AsyncClient); /health/db — через dependency_overrides;
            test_user_model.py и test_auth.py ──▶ реальная БД (skip, если недоступна);
            test_llm.py ──▶ MockProvider (без сети), OpenAI — skip без ключа
```

**Frontend** (запросы к backend через единый клиент; CORS разрешает `http://localhost:5173`):

```text
src/main.tsx ──▶ QueryClientProvider + BrowserRouter
    └──▶ src/App.tsx ──▶ src/pages/*
              ├── LoginPage ──▶ src/api/client.ts (POST /auth/register, POST /auth/login)
              │                     └──▶ src/lib/tokens.ts (сохранить токены)
              └── DashboardPage ──▶ src/api/client.ts (GET /me, Bearer)
                                    └──▶ src/lib/tokens.ts (чтение/очистка)
    └──▶ src/components/ui/* (shadcn/ui)
```

Типы запросов/ответов frontend берёт из `src/api/schema.d.ts`, который генерируется
из OpenAPI backend (`npm run generate:api`, нужен запущенный backend).

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
| Миграции БД | `backend/alembic/` (`uv run alembic ...`) | 3 миграции: pgvector, users, agent_actions |
| Прогон тестов backend | `backend/tests/` (pytest) | 47 тестов (1 пропускается без ключа OpenAI) |
| Frontend dev-сервер | `frontend/` (`npm run dev`) | вход/регистрация через API |
| Генерация типов API | `frontend/` (`npm run generate:api`, нужен backend) | скрипт готов |
| Сборка frontend | `npm run build` (tsc + vite) | проходит |

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
| `LLM_PROVIDER` | провайдер LLM: `mock` (по умолчанию) или `openai` | нет |
| `OPENAI_API_KEY` | ключ OpenAI (нужен для `LLM_PROVIDER=openai`) | да |
| `OPENAI_MODEL` | модель OpenAI (нужна для `LLM_PROVIDER=openai`) | нет |
| `CORS_ORIGINS` | браузерные источники (JSON-массив; по умолчанию `["http://localhost:5173"]`) | нет |
| `AGENT_MAX_STEPS` | максимум шагов агентского цикла (по умолчанию 10) | нет |
| `AGENT_TOKEN_BUDGET` | бюджет токенов на цикл (по умолчанию 50000) | нет |
| `AGENT_TIMEOUT_SECONDS` | общий таймаут цикла, сек (по умолчанию 120) | нет |
| `AGENT_TOOL_TIMEOUT_SECONDS` | таймаут одного инструмента, сек (по умолчанию 30) | нет |

### `backend/pyproject.toml` и `backend/alembic.ini`

- `pyproject.toml` — зависимости, dev-группа, конфигурация pytest и ruff.
- `alembic.ini` — расположение миграций и логирование; URL БД задаётся в `alembic/env.py`.

### `frontend/`

- `package.json` — зависимости и npm-скрипты (`dev`, `build`, `lint`, `preview`, `generate:api`).
- `.env.example` — `VITE_API_BASE_URL` (копируется в `frontend/.env` при необходимости).
- `.npmrc` — `save-exact=true` (фиксация версий).
- `vite.config.ts` — React + Tailwind 4 (`@tailwindcss/vite`), алиас `@/*`.
- `tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json` — TypeScript (алиас `@/*`).
- `components.json` — конфигурация shadcn/ui.
- `.oxlintrc.json` — линтер (react/only-export-components отключён для `components/ui`).

### Прочие конфигурационные файлы

- `.editorconfig` — единый стиль форматирования.
- `.gitattributes` — нормализация переводов строк.
- `.gitignore` — исключения git (корневой и `frontend/.gitignore`).
- `backend/.python-version` — пин Python 3.13 для uv.

### Отсутствуют (План)

`Dockerfile` приложений, CI-конфигурация — появятся вместе с кодом.

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
- Таблица `agent_actions` (миграция `22cd6bbf10ed`): аудит-лог действий агента — шаг, tool,
  аргументы и результат (JSONB), статус, токены, длительность; `session_id` — свободная ссылка
  без FK (сессии появятся на неделе 5).

**План** ([`AGENTS.md`](../AGENTS.md) §4–5):

- Остальные таблицы схемы: `resumes`, `vacancies`, `topics`, `topic_prerequisites`,
  `user_skill_states`, `interview_sessions` / `interview_turns`, `agent_actions`,
  `learning_plans` / `plan_items`, `embeddings` (pgvector).
- ORM-модели (SQLAlchemy 2) — от `Base` в `backend/app/db/base.py`; миграции — autogenerate.
- Граф знаний на MVP — реляционная модель в Postgres, доступ через репозиторий-границу.

---

## 9. Внешние интеграции

**Факт:** в рантайме внешних вызовов нет. Реализован слой LLM: провайдер-агностичный интерфейс,
`MockProvider` (по умолчанию, без сети) и `OpenAIProvider` на официальном SDK; живые вызовы
выполняются только при `LLM_PROVIDER=openai` с ключом и моделью.

**План** ([`AGENTS.md`](../AGENTS.md) §6): использование LLM в продукте — через Agent Harness
(LLM выбирает инструменты, Harness их исполняет и пишет audit-лог). Данные в LLM: тексты
заданий/ответов, структурированный JSON (tool-calls, оценки).

---

## 10. Тесты

**Backend.** `backend/tests/` — 47 тестов на pytest (+ `pytest-asyncio`):

- `test_health.py` — `/health` (200 + статус) и `/docs` (200);
- `test_health_db.py` — `/health/db`: 200 и 503 (два случая: `SQLAlchemyError`, `OSError`)
  через подмену зависимости `get_db`; реальная БД не требуется;
- `test_user_model.py` — интеграционный: вставка/чтение `User` в реальной БД; пропускается
  без PostgreSQL;
- `test_auth.py` — интеграционные тесты auth (register/login/me/refresh + негативные кейсы)
  через `httpx2.AsyncClient` + `ASGITransport`;
- `test_cors.py` — CORS-заголовки и preflight для frontend-origin;
- `test_llm.py` — MockProvider и фабрика без сети; живой тест OpenAI пропускается без ключа;
- `test_agent_tools.py` — реестр инструментов и исполнитель: валидация аргументов, ошибки
  обработчика, таймаут, аудит-записи (без БД);
- `test_agent_harness.py` — граф LangGraph на мок-LLM: полный цикл с инструментом, лимиты
  шагов/токенов, таймаут, ошибки LLM и инструмента, продолжение истории по `thread_id`;
- `test_agent_audit.py` — запись/чтение аудит-лога в реальной БД; пропускается без PostgreSQL.

Запуск: `uv run pytest` из `backend/`. Конфигурация — в `backend/pyproject.toml`
(`testpaths`, `pythonpath`, `asyncio_mode`).

**Frontend.** Автотестов нет; проверки — `npm run build` (типы + сборка) и `npm run lint`
(oxlint). Сквозной сценарий (регистрация → вход → `/me` → перезагрузка → выход → ошибка пароля)
проверен вручную в браузере на dev-сервере.

**План** ([`AGENTS.md`](../AGENTS.md) §9): функциональные тесты, агентские (на мок-LLM),
сценарные e2e, тесты адаптивности, eval-наборы качества LLM.

---

## 11. Скрипты

- **Backend:** каталога `scripts/` и `Makefile` нет; команды — в
  [`backend/README.md`](../backend/README.md) (`uv sync`, `uv run uvicorn`, `uv run pytest`,
  `uv run ruff`, `uv run alembic upgrade head`).
- **Frontend:** npm-скрипты в `frontend/package.json` — `dev`, `build` (`tsc -b && vite build`),
  `lint` (oxlint), `preview`, `generate:api` (типы из OpenAPI, нужен запущенный backend).
- **Инфраструктура:** команды `docker compose` из [`infra/README.md`](../infra/README.md).

---

## 12. Генерируемые файлы

- `backend/uv.lock` — генерируется uv; коммитится; вручную не редактируется.
- `backend/alembic/versions/*` — файлы миграций (генерация `alembic revision`); коммитятся;
  применённые ревизии вручную не редактируются.
- `frontend/src/api/schema.d.ts` — типы из OpenAPI (генерация `npm run generate:api`); коммитится;
  вручную не редактируется.
- `frontend/package-lock.json` — генерируется npm; коммитится; вручную не редактируется.
- `frontend/src/components/ui/*` — генерируются shadcn CLI (править только осознанно).
- Локальные/игнорируемые: `backend/.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`,
  `frontend/node_modules/`, `frontend/dist/`, `*.log` — перечислены в `.gitignore` и
  `frontend/.gitignore`.
- `infra/.env` и `backend/.env` — локальные файлы (копии `.env.example`), в git не попадают.
