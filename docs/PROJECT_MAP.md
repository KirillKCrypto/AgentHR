# PROJECT_MAP — карта репозитория AgentHR

> Навигация: [`INDEX.md`](../INDEX.md) → **PROJECT_MAP.md** (этот файл) → [`ARCHITECTURE.md`](ARCHITECTURE.md).
> Составлено по состоянию на 22.10.2026.
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
| `backend/` | APPLICATION | FastAPI (`/health`, `/health/db`, JWT-auth, слой LLM, Agent Harness, миграции, тесты) + Dockerfile |
| `frontend/` | APPLICATION | SPA-каркас: Vite + React 19 + TS, Tailwind 4, shadcn/ui; вход/регистрация через API |
| `infra/` | INFRASTRUCTURE | локальная инфраструктура в Docker Compose: PostgreSQL 16 + pgvector и backend API в контейнере |
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
│   ├── .dockerignore          (исключения контекста сборки образа)
│   ├── .env.example
│   ├── .env                   (локальный, в git не попадает)
│   ├── .python-version        (пин Python 3.13)
│   ├── Dockerfile             (образ backend: uv, без dev-зависимостей)
│   ├── README.md
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py             (настройка миграций, URL из настроек)
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 6d7c8a1b787e_enable_pgvector_extension.py
│   │       ├── 22cd6bbf10ed_create_agent_actions_table.py
│   │       ├── 40b5a867f0dc_create_knowledge_graph_and_documents.py
│   │       └── 68cf3aa5da9d_create_users_table.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            (точка входа FastAPI; CORS, роутеры, /health, /health/db)
│   │   ├── agent/
│   │   │   ├── __init__.py    (реэкспорт реестра, аудита, harness'ов)
│   │   │   ├── analysis_tools.py (7 доменных инструментов, привязанных к пользователю)
│   │   │   ├── audit.py       (AgentActionRecord, AuditLogger, InMemory/Db)
│   │   │   ├── deep_harness.py (DeepAgentHarness: create_deep_agent, лимиты, checkpointer)
│   │   │   ├── langchain_model.py (ProviderChatModel: наш LLMProvider → LangChain)
│   │   │   ├── langchain_tools.py (RegistryTool: ToolRegistry → инструменты LangChain)
│   │   │   ├── middleware.py  (AuditMiddleware, LimitsMiddleware, текст ошибок инструментов)
│   │   │   ├── result.py      (AgentRunResult — общий контракт результата)
│   │   │   └── tools.py       (ToolDefinition, ToolRegistry, JSON Schema)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py        (get_current_user, LLM/эмбеддер, алиасы зависимостей)
│   │   │   ├── mappers.py     (доменные объекты → Pydantic-схемы)
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── analysis.py (POST /analysis)
│   │   │       ├── auth.py    (register, login, refresh)
│   │   │       ├── profile.py (/profile, /profile/gaps)
│   │   │       ├── resumes.py (/resumes, /resumes/{id})
│   │   │       ├── users.py   (/me)
│   │   │       └── vacancies.py (/vacancies, /vacancies/{id})
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py      (настройки, pydantic-settings)
│   │   │   └── security.py    (argon2-хеши, JWT)
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py        (Base для моделей)
│   │   │   └── session.py     (async-движок, get_db)
│   │   ├── embeddings/
│   │   │   ├── __init__.py    (реэкспорт слоя эмбеддингов)
│   │   │   ├── base.py        (EmbeddingProvider, косинусная близость, заглушка)
│   │   │   ├── factory.py     (выбор провайдера по настройкам)
│   │   │   ├── local.py       (локальная ONNX-модель через fastembed)
│   │   │   └── mock.py        (детерминированный провайдер для тестов)
│   │   ├── llm/
│   │   │   ├── __init__.py    (реэкспорт интерфейса и реализаций)
│   │   │   ├── base.py        (типы и Protocol LLMProvider)
│   │   │   ├── factory.py     (выбор провайдера по настройкам)
│   │   │   ├── mock.py        (MockProvider для тестов)
│   │   │   └── openai.py      (OpenAIProvider, SDK openai, DeepSeek/OpenAI-совместимые API)
│   │   ├── models/
│   │   │   ├── __init__.py    (импортирует все модели для Alembic)
│   │   │   ├── agent_action.py (модель AgentAction)
│   │   │   ├── ontology_review.py (модель OntologyReviewAction)
│   │   │   ├── resume.py      (модели Resume, ResumeSkill)
│   │   │   ├── topic.py       (модели Topic, TopicAlias, TopicPrerequisite, TopicCandidate)
│   │   │   ├── user.py        (модель User)
│   │   │   ├── user_skill_state.py (модель UserSkillState)
│   │   │   └── vacancy.py     (модели Vacancy, VacancySkill)
│   │   ├── ontology/
│   │   │   ├── __init__.py    (реэкспорт онтологии и операций над графом)
│   │   │   ├── graph.py       (циклы, топологический порядок, пререквизиты)
│   │   │   ├── seed.py        (идемпотентный сид + CLI)
│   │   │   └── topics.py      (онтология v2: 89 атомарных тем, алиасы, зависимости)
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── analysis.py    (схемы вакансий, резюме, профиля и gap-анализа)
│   │   │   └── auth.py        (Pydantic-схемы auth)
│   │   └── services/
│   │       ├── __init__.py    (реэкспорт сервисного слоя)
│   │       ├── analysis.py    (извлечение навыков вакансии и резюме)
│   │       ├── evaluation.py  (precision / recall / F1)
│   │       ├── normalization.py (сопоставление навыка с темой онтологии)
│   │       ├── profile.py     (запись документов, профиль, gap-анализ)
│   │       └── topics.py      (индекс тем из БД и из пакета онтологии)
│   ├── docker/
│   │   └── entrypoint.sh      (миграции + uvicorn в контейнере)
│   ├── pyproject.toml
│   ├── tests/
│   │   ├── conftest.py        (фикстуры: БД, пользователь API, заглушка LLM по схеме)
│   │   ├── test_health.py
│   │   ├── test_health_db.py
│   │   ├── test_user_model.py
│   │   ├── test_auth.py
│   │   ├── test_cors.py
│   │   ├── test_llm.py
│   │   ├── test_agent_tools.py
│   │   ├── test_agent_deep_harness.py
│   │   ├── test_agent_audit.py
│   │   ├── test_ontology.py
│   │   ├── test_ontology_graph.py
│   │   ├── test_ontology_seed.py
│   │   ├── test_analysis.py
│   │   ├── test_analysis_api.py   (доменные эндпоинты, изоляция по пользователю)
│   │   ├── test_analysis_tools.py (инструменты агента и их схемы)
│   │   ├── test_profile_service.py (взвешивание оценок, источники истины)
│   │   ├── test_embeddings.py
│   │   ├── test_embeddings_local.py
│   │   ├── test_extraction_golden.py
│   │   ├── test_normalization.py
│   │   └── fixtures/
│   │       ├── __init__.py
│   │       └── extraction_golden.py (golden-набор извлечения навыков)
│   ├── scripts/
│   │   └── eval_extraction.py     (eval качества извлечения на живой модели)
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

**Назначение:** локальная инфраструктура разработки — два сервиса: `postgres` (PostgreSQL 16
+ pgvector) и `api` (backend-приложение в контейнере, образ собирается из `backend/Dockerfile`).

**Содержит:** `docker-compose.yml`, `.env.example`, `.env` (локальный), `README.md`.

**Зависит от:** Docker Desktop; `backend/Dockerfile` (для сервиса `api`); значений переменных
из `infra/.env` (в том числе `API_PORT`, `LLM_*`, `JWT_SECRET_KEY` — передаются в контейнер API).

**Используется:** разработчиками (команды `docker compose`); backend-приложение обращается
к БД внутри compose-сети по имени сервиса (`postgres:5432`), снаружи БД доступна
по `localhost:${POSTGRES_PORT}` (для локального запуска backend и инструментов).

**Важно:** данные хранятся в named volume `agenthr_postgres_data`; удаляются только
`docker compose down -v`. Порт `POSTGRES_PORT` может занимать другой проект
(например, стек Airflow) — при конфликте освободить порт или сменить значение.

### `backend/`

**Role:** APPLICATION (backend)

**Назначение:** backend-приложение AgentHR. Реализованы: FastAPI-точка входа
(`app/main.py`: CORS, роутеры, `/health`, `/health/db`, обработчик `LLMError`), JWT-аутентификация
(`app/api/`, `app/core/security.py`), слой LLM (`app/llm/`: интерфейс, mock- и OpenAI-совместимый
провайдеры, основной — DeepSeek),
агентский слой (`app/agent/`: реестр Tools, middleware аудита и лимитов, harness на Deep Agents,
доменные инструменты), онтология v2 с сидом (`app/ontology/`), сервисный слой
(`app/services/`: извлечение, нормализация, профиль и gap-анализ), доменные REST-эндпоинты
(`/vacancies`, `/resumes`, `/profile`, `/analysis`), настройки (`app/core/config.py`), слой БД
(`app/db/`), модели (`app/models/`: пользователь, аудит-лог, граф знаний, документы, срез профиля),
миграции (`alembic/`), тесты (`tests/`), зависимости через uv.

**Цель по плану:** планировщик подготовки, сессии интервью с адаптацией сложности, отчёты
([`AGENTS.md`](../AGENTS.md) §2–3, §6, §8).

**Содержит сейчас:** `app/` (agent, api, core, db, embeddings, llm, models, ontology, schemas,
services), `alembic/`, `alembic.ini`, `scripts/`, `tests/`, `pyproject.toml`, `uv.lock`,
`.env.example`, `.python-version`, `README.md`.
Поток A (вакансия + резюме → профиль знаний → gap-анализ) реализован и покрыт тестами.

### `frontend/`

**Role:** APPLICATION (frontend)

**Назначение:** React SPA AgentHR. Реализованы: вход через UI, экран новой подготовки
(`/vacancies/new`: тексты вакансии и резюме → `POST /vacancies` → `POST /resumes` →
`POST /analysis`, вывод требований, готовности и разрывов), профиль знаний (`/profile`:
темы 0–100 с источником и уверенностью, подсветка пробелов по выбранной вакансии,
блок навыков вне онтологии, `?vacancy=<id>`), дашборд (загрузка `/me` и списка вакансий,
переходы к подготовке и профилю, выход), 404. Стек: Vite + React 19 + TypeScript,
Tailwind CSS 4, shadcn/ui (Base UI), роутинг (react-router 8), TanStack Query;
типизированный API-клиент (`src/api/client.ts`, типы из OpenAPI в `src/api/schema.d.ts`).

**Цель по плану:** остальные экраны продукта — `/plans/:id`, `/interview/:id`,
`/reports/:id` ([`AGENTS.md`](../AGENTS.md) §7). Источник: `frontend/README.md`.

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

**Responsibility:** описывает два сервиса проекта `agenthr`: `postgres` (образ
`pgvector/pgvector:pg16`, контейнер `agenthr-postgres`, порт `${POSTGRES_PORT}:5432`, volume
`postgres_data`, healthcheck `pg_isready`) и `api` (сборка из `../backend`, контейнер
`agenthr-api`, порт `${API_PORT:-8000}:8000`, `depends_on` healthy-БД, `DATABASE_URL`
на `postgres:5432`, healthcheck через `/health`).

**Depends on:** `infra/.env` (подстановка переменных), Docker Desktop, `backend/Dockerfile`.

**Used by:** локальный запуск БД и API для всей команды; frontend обращается к API
по `localhost:${API_PORT}`.

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

#### `backend/Dockerfile`

**Role:** DEPLOYMENT

**Responsibility:** образ backend-приложения: `python:3.13-slim`, uv зафиксированной версии
(из `ghcr.io/astral-sh/uv`), зависимости из `uv.lock` (`uv sync --frozen --no-dev`), код
и миграции внутри образа, `ENTRYPOINT /app/docker/entrypoint.sh`, `EXPOSE 8000`.

**Depends on:** `backend/pyproject.toml`, `backend/uv.lock`, `backend/docker/entrypoint.sh`.

**Used by:** сервис `api` в `infra/docker-compose.yml`.

**Important:** dev-зависимости (тесты, ruff) в образ не входят; после изменения кода нужна
пересборка (`docker compose up -d --build`).

#### `backend/docker/entrypoint.sh`

**Role:** DEPLOYMENT

**Responsibility:** запуск backend в контейнере: `alembic upgrade head`, затем
`uvicorn app.main:app --host 0.0.0.0 --port 8000` (число воркеров — `UVICORN_WORKERS`).

**Depends on:** `backend/alembic/`, `backend/app/`.

**Used by:** `backend/Dockerfile` (`ENTRYPOINT`).

**Important:** миграции применяются автоматически при старте контейнера; неудачная миграция
останавливает контейнер, а не поднимает приложение с устаревшей схемой.

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
`REFRESH_TOKEN_EXPIRE_DAYS`, `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`,
`LLM_STRUCTURED_MODE`, `CORS_ORIGINS`.

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

#### `backend/app/models/topic.py`

**Role:** MODEL (граф знаний)

**Responsibility:** ORM-модели `Topic` (тема онтологии: `key`, `name`, `description` — текст
для эмбеддингов, `category`, `aliases`, `ontology_version`, `is_auto_generated`),
`TopicPrerequisite` (ребро `REQUIRES`, запрет саморебра) и `TopicCandidate` (навык вне
онтологии: `normalized_name` уникален, `occurrences`, `sources`, `status`).

**Depends on:** `backend/app/db/base.py`.

**Used by:** `backend/app/ontology/seed.py`, Alembic (autogenerate); далее — сервис анализа.

**Important:** онтология — словарь, а не фильтр: `topic_candidates` не даёт потерять навыки
без темы.

#### `backend/app/models/vacancy.py`, `backend/app/models/resume.py`

**Role:** MODEL (документы пользователя)

**Responsibility:** `Vacancy` и `Resume` (текст, заголовок, владелец) + `VacancySkill`
(`required_level` 0–100, `weight`, `confidence`, `evidence`, `match_method`) и `ResumeSkill`
(`proficiency` 0–100, `confidence`, `evidence`, `match_method`). У навыка `topic_id` может
быть NULL — навык не сопоставлен ни с одной темой и сохраняется как есть.

**Depends on:** `backend/app/db/base.py`.

**Used by:** сервис анализа (M2), REST API (M2), Alembic (autogenerate).

**Important:** при удалении темы `topic_id` обнуляется (ON DELETE SET NULL) — данные не теряются.

#### `backend/app/models/user_skill_state.py`

**Role:** MODEL (срез профиля)

**Responsibility:** `UserSkillState` — материализованный срез графа для пользователя:
уникальная пара `(user_id, topic_id)`, `proficiency` 0–100, `confidence`, `source`,
`evidence` (JSONB), `last_assessed`.

**Depends on:** `backend/app/db/base.py`.

**Used by:** сервис анализа и gap-анализ (M2), REST API профиля (M2), Alembic (autogenerate).

**Important:** источник оценки (`source`) разделяет резюме, интервью и ручную правку —
на него опирается взвешенное обновление профиля.

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

**Used by:** `backend/app/agent/langchain_tools.py` (адаптер для Deep Agents);
в будущем — конкретные инструменты.

**Important:** каждый инструмент обязан иметь JSON Schema; повторная регистрация имени запрещена.

#### `backend/app/agent/deep_harness.py`

**Role:** AGENT (оркестратор — основной harness проекта)

**Responsibility:** `DeepAgentHarness` — сборка агента через `deepagents.create_deep_agent`
(файловая система и суммаризация контекста из коробки, checkpoint по `thread_id`), подключение
middleware аудита/лимитов и обработчика ошибок инструментов, возврат результата в общем контракте
`AgentRunResult` (статус, сообщения, шаги, токены). Лимиты — `AGENT_MAX_STEPS`,
`AGENT_TOKEN_BUDGET`, `AGENT_TIMEOUT_SECONDS`; таймаут — на весь прогон.

**Depends on:** `app/agent/langchain_model.py`, `app/agent/langchain_tools.py`,
`app/agent/middleware.py`, `app/agent/audit.py`, `app/agent/result.py`, `deepagents`.

**Used by:** будущие агентские сценарии (M2+); тесты `backend/tests/test_agent_deep_harness.py`.

**Important:** агент обязан собираться с нашими middleware — иначе вызовы не попадут в аудит
и цикл не будет ограничен. `deepagents` ставит `recursion_limit=9999`, поэтому лимит шагов
держим в `LimitsMiddleware` (она останавливает цикл раньше).

#### `backend/app/agent/middleware.py`

**Role:** AGENT (правила проекта в цикле агента)

**Responsibility:** `AuditMiddleware` — запись в `agent_actions` каждого вызова модели
(шаг, токены) и каждого вызова инструмента (аргументы, результат, длительность, статус);
`LimitsMiddleware` — остановка цикла по числу шагов и бюджету токенов с понятным сообщением;
`tool_error_text` — текст ошибки инструмента, который возвращается модели (цикл не прерывается).

**Depends on:** `app/agent/audit.py`, `app/agent/tools.py`, `langchain.agents.middleware`.

**Used by:** `backend/app/agent/deep_harness.py`.

**Important:** состояние прогона (`audit_step`, `run_model_calls`, токены) — untracked, то есть
не сохраняется в checkpoint; в checkpoint попадает только `run_status` (причина остановки).

#### `backend/app/agent/langchain_model.py`

**Role:** AGENT (адаптер LLM-слоя)

**Responsibility:** `ProviderChatModel` — LangChain-модель (`BaseChatModel`) поверх нашего
`LLMProvider`: конвертация сообщений в обе стороны, передача JSON Schema инструментов
и `usage_metadata` с токенами. Нужен, чтобы Deep Agents работал на нашем провайдер-агностичном
слое (включая `MockProvider` в тестах).

**Depends on:** `app/llm/base.py`, `langchain-core`.

**Used by:** `backend/app/agent/deep_harness.py`.

**Important:** поддерживается только async-путь (`_agenerate`) — обработчики инструментов и
провайдеры асинхронные; синхронный вызов бросает `NotImplementedError`.

#### `backend/app/agent/langchain_tools.py`

**Role:** AGENT (адаптер инструментов)

**Responsibility:** `RegistryTool` — инструмент LangChain из записи `ToolRegistry`: модель
получает нашу JSON Schema дословно (`tool_call_schema`), аргументы валидируются реестром,
обработчик вызывается с таймаутом; `build_registry_tools` собирает список для Deep Agents.

**Depends on:** `app/agent/tools.py`, `langchain-core`.

**Used by:** `backend/app/agent/deep_harness.py`.

**Important:** схема инструмента не пересобирается в pydantic-модель — так JSON Schema
описаний остаётся единственным источником правды для LLM.

#### `backend/app/agent/result.py`

**Role:** AGENT (контракт результата)

**Responsibility:** `AgentRunResult` — статус, сообщения, финальный текст, шаги, токены, ошибка.
Единый контракт результата прогона агента.

**Used by:** `backend/app/agent/deep_harness.py`, тесты.

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
`get_llm_provider` — провайдер на время запроса с закрытием клиента; `get_embedder` —
единый кэшированный провайдер эмбеддингов; алиасы `CurrentUser`, `DbSession`, `LlmProvider`,
`Embedder` для аннотаций роутеров.

**Depends on:** `backend/app/core/security.py`, `backend/app/db/session.py`,
`backend/app/models/`, `app/llm/factory.py`, `app/embeddings/factory.py`.

**Used by:** все защищённые роутеры (`/me`, `/vacancies`, `/resumes`, `/profile`, `/analysis`).

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

#### `backend/app/api/routes/vacancies.py`, `resumes.py`

**Role:** API (документы)

**Responsibility:** `POST /vacancies` — извлечение требований LLM и запись вакансии с навыками;
`GET /vacancies` — список без навыков; `GET /vacancies/{id}` — карточка с навыками.
`POST /resumes` — извлечение навыков, запись и пересборка профиля; `GET /resumes`,
`GET /resumes/{id}` — список и карточка. Ошибки: 422 — нечитаемый ответ модели,
404 — чужой/несуществующий документ, 502 — LLM недоступна (глобальный обработчик).

**Depends on:** `app/services/profile.py`, `app/api/mappers.py`, `app/api/deps.py`.

**Used by:** подключаются в `backend/app/main.py`; далее — экраны загрузки и профиля.

#### `backend/app/api/routes/profile.py`, `analysis.py`

**Role:** API (профиль и анализ)

**Responsibility:** `GET /profile` — срез профиля знаний и навыки вне онтологии;
`GET /profile/gaps?vacancy_id=...` — разрывы и готовность к вакансии; `POST /analysis` —
документы, профиль и gap-анализ одним ответом. `POST /analysis` LLM не вызывает:
извлечение выполняется при загрузке документов.

**Depends on:** `app/services/profile.py`, `app/api/mappers.py`.

**Used by:** подключаются в `backend/app/main.py`; дашборд и экран профиля.

#### `backend/app/api/mappers.py`

**Role:** API (маппинг)

**Responsibility:** преобразование доменных dataclass-объектов сервисного слоя
(`SkillEntry`, `ProfileSnapshot`, `GapReport`, `Vacancy`, `Resume`) в Pydantic-схемы API.
Единая точка, чтобы сервисы не зависели от схем транспорта.

**Depends on:** `app/schemas/analysis.py`, `app/services/profile.py`.

**Used by:** доменные роутеры.

#### `backend/app/schemas/analysis.py`

**Role:** SCHEMA (DTO)

**Responsibility:** схемы `VacancyCreate/Read/Summary`, `ResumeCreate/Read/Summary`, `SkillRead`,
`TopicBrief`, `ProfileRead`/`ProfileTopicRead`, `UnmatchedSkillRead`, `GapAnalysisRead`/`GapItemRead`,
`AnalysisRequest/Response`. Ограничение текста документа — 50 000 символов.

**Depends on:** `pydantic`.

**Used by:** доменные роутеры, `app/api/mappers.py`; типы попадают в OpenAPI и генерируются
во frontend.

#### `backend/app/services/profile.py`

**Role:** SERVICE (документы, профиль, gap-анализ)

**Responsibility:** `analyze_vacancy` / `save_vacancy_analysis`, `analyze_resume` /
`save_resume_analysis` — извлечение и запись документов с нормализацией навыков;
`rebuild_profile` — пересчёт среза по резюме без занижения более сильных источников;
`get_profile`, `compute_gaps`, `update_skill_proficiency`, `weighted_estimate` — профиль,
разрывы, `coverage_all` / `confirmed_readiness` и взвешенное слияние оценок.
`NotFoundError` — изоляция по владельцу.

**Depends on:** `app/services/analysis.py`, `app/services/topics.py`,
`app/models/`, `app/llm/base.py`, `app/embeddings/base.py`.

**Used by:** доменные роутеры, `app/agent/analysis_tools.py`, тесты.

**Important:** веса источников — `manual 1.0 / interview 0.9 / assessment 0.8 / resume 0.6`;
потолок уверенности `0.95`; `coverage_all` включает provisional-темы,
`confirmed_readiness` — только canonical; группы `OR` считаются по max, `AND` — по min;
`criticality` (`must_have`/`nice_to_have`) сохраняется и отдаётся в gap-анализе.

#### `backend/app/agent/analysis_tools.py`

**Role:** AGENT (доменные инструменты)

**Responsibility:** 7 инструментов с JSON Schema: `extract_vacancy_requirements`,
`extract_resume_skills`, `get_vacancy_requirements`, `get_user_skill_state`,
`query_skill_dependencies`, `update_skill_proficiency`, `compute_vacancy_gaps`.
`build_analysis_tools` / `register_analysis_tools` собирают их под пользователя и сессию БД.

**Depends on:** `app/agent/tools.py`, `app/services/analysis.py`, `app/services/profile.py`,
`app/models/topic.py`.

**Used by:** агентские сценарии (M3–M4), тесты `test_analysis_tools.py`.

**Important:** `user_id` не приходит от модели — агент физически не может обратиться к чужим данным.

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
(`generate_with_tools`), структурированный вывод по JSON Schema (`generate_structured`).
Режим задаётся `LLM_STRUCTURED_MODE`: `json_schema` — `response_format: json_schema` со
`strict` и откатом в промпт; `json_object` — схема в промпте + `response_format: json_object`
(DeepSeek); `prompt` — только схема в промпте. Конвертация сообщений и usage; таймаут и
повторы — из настроек; ошибки SDK оборачиваются в `LLMError`.

**Depends on:** `openai`, `backend/app/llm/base.py`.

**Used by:** `backend/app/llm/factory.py`.

**Important:** секреты — только из настроек; живой вызов проверяется тестом со `skipif`
без ключа (`RUN_LIVE_LLM_TESTS=1`).

#### `backend/app/llm/factory.py`

**Role:** LLM (конфигурация)

**Responsibility:** `create_llm_provider(settings)` — выбор провайдера по `LLM_PROVIDER`
(`mock` по умолчанию; `openai` требует `OPENAI_API_KEY` и `OPENAI_MODEL`; для DeepSeek —
`OPENAI_BASE_URL=https://api.deepseek.com`, `OPENAI_MODEL=deepseek-flash`,
`LLM_STRUCTURED_MODE=json_object`).

**Depends on:** `backend/app/core/config.py`, `backend/app/llm/*`.

**Used by:** точки сборки приложения/скриптов (в `main.py` пока не подключён).

#### `backend/app/agent/audit.py`

**Role:** AGENT (аудит)

**Responsibility:** `AgentActionRecord`, Protocol `AuditLogger`, реализации:
`InMemoryAuditLogger` (тесты без БД) и `DbAuditLogger` (запись в таблицу `agent_actions`).

**Depends on:** `backend/app/models/agent_action.py`.

**Used by:** `backend/app/agent/middleware.py` (аудит текущего цикла).

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
фабрика: mock по умолчанию, требования к openai-конфигурации, режимы structured output) +
живой тест внешнего API со `skipif` без `OPENAI_API_KEY`/`OPENAI_MODEL`.

**Depends on:** `backend/app/llm/*`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_agent_tools.py`

**Role:** TEST

**Responsibility:** тесты реестра и исполнителя без БД: дубликаты имён, `specs()`, валидация
аргументов, успешное исполнение с аудит-записью, невалидные аргументы без вызова обработчика,
ошибка обработчика, таймаут.

**Depends on:** `backend/app/agent/*`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_agent_deep_harness.py`

**Role:** TEST

**Responsibility:** тесты основного harness (Deep Agents) на мок-LLM: полный цикл с инструментом
и аудитом (шаги и токены), дословная передача JSON Schema инструмента модели, лимит шагов, бюджет
токенов, таймаут, ошибка LLM, ошибка инструмента и невалидные аргументы (возврат в модель),
продолжение истории по `thread_id` (checkpoint).

**Depends on:** `backend/app/agent/deep_harness.py`, `app/llm` (MockProvider).

**Used by:** `uv run pytest`.

#### `backend/tests/test_agent_audit.py`

**Role:** TEST

**Responsibility:** интеграционный тест `DbAuditLogger`: запись и чтение строки
из `agent_actions` в реальной БД; пропускается без PostgreSQL.

**Depends on:** `backend/app/agent/audit.py`, `backend/app/db/session.py`.

**Used by:** `uv run pytest`.

#### `backend/tests/conftest.py`

**Role:** TEST (фикстуры)

**Responsibility:** общие фикстуры интеграционных тестов: `seeded_db` (пропуск без PostgreSQL +
засеянная онтология), `api_user` (регистрация, логин, подмена `get_llm_provider` и `get_embedder`),
`second_user` (проверка изоляции), `SchemaStubProvider` — LLM-заглушка, отдающая ответ
по имени JSON-схемы; тексты вакансии и резюме для тестов.

**Depends on:** `app.main`, `app.db.session`, `app.api.deps`, `app.ontology.seed`.

**Used by:** `test_analysis_api.py`, `test_analysis_tools.py` и другие интеграционные тесты.

#### `backend/tests/test_analysis_api.py`

**Role:** TEST

**Responsibility:** доменные эндпоинты: создание вакансии с извлечением и сопоставлением навыков,
резюме и пересборка профиля, `/analysis` с разрывами и готовностью, списки документов,
изоляция по пользователю (404 на чужое), 401 без токена, 422 на пустой текст, 502 при сбое LLM.

**Depends on:** `tests/conftest.py`, `app.main`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_analysis_tools.py`

**Role:** TEST

**Responsibility:** инструменты агента: набор имён и JSON Schema, валидация аргументов,
извлечение без записи в БД, изоляция по владельцу, чтение профиля, пререквизиты графа,
обновление оценки, ошибка невалидного UUID.

**Depends on:** `app.agent.analysis_tools`, `app.services.profile`, `tests/conftest.py`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_profile_service.py`

**Role:** TEST

**Responsibility:** взвешивание оценок (`weighted_estimate`: среднее по уверенности, потолок
`0.95`, нулевая уверенность), сохранение оценки интервью при пересборке по резюме, слияние
ручной оценки с резюме, ошибка на неизвестной теме.

**Depends on:** `app.services.profile`, `app.db.session`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_ontology.py`, `backend/tests/test_ontology_graph.py`

**Role:** TEST

**Responsibility:** состав онтологии v1 (уникальные ключи, заполненные описания и алиасы,
пререквизиты ссылаются на существующие темы, граф ацикличен) и операции над графом
(поиск циклов, топологический порядок, транзитивные пререквизиты). Без БД.

**Depends on:** `backend/app/ontology/`.

**Used by:** `uv run pytest`.

#### `backend/tests/test_ontology_seed.py`

**Role:** TEST

**Responsibility:** интеграционный тест сида: темы и связи созданы, повторный сид
идемпотентен, изменённое описание восстанавливается, автосозданные темы сохраняются.
Пропускается без PostgreSQL.

**Depends on:** `backend/app/ontology/seed.py`, `backend/app/models/`, `backend/app/db/session.py`.

**Used by:** `uv run pytest`.

#### `backend/.env.example`

**Role:** CONFIG (шаблон)

**Responsibility:** шаблон локальных настроек backend: `APP_NAME`, `ENVIRONMENT`, `DATABASE_URL`,
`JWT_*`, `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`,
`LLM_STRUCTURED_MODE`, `CORS_ORIGINS`. Копируется в `backend/.env` (в git не попадает).

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

#### `backend/app/ontology/topics.py`

**Role:** DOMAIN (онтология)

**Responsibility:** онтология v2 — 89 атомарных тем и 75 пререквизитов
(`OntologyTopic`: ключ, название, описание, категория, алиасы, пререквизиты) и версия
`ONTOLOGY_VERSION`. Описания тем используются как текст для эмбеддингов при
нормализации навыков. Состав и ограничения описаны в [`docs/ONTOLOGY.md`](ONTOLOGY.md).

**Depends on:** — (только стандартная библиотека).

**Used by:** `backend/app/ontology/seed.py`, тесты; далее — сервис нормализации.

**Important:** онтология — стартовое ядро, а не whitelist: навыки вне словаря не теряются,
а попадают в кандидаты на новые темы.

#### `backend/app/ontology/graph.py`

**Role:** DOMAIN (операции над графом)

**Responsibility:** работа с рёбрами `REQUIRES` без привязки к ORM: поиск циклов
(`detect_cycles`), топологический порядок (`topological_order`), прямые и транзитивные
пререквизиты.

**Depends on:** — (только стандартная библиотека).

**Used by:** тесты; далее — планировщик (M3) и gap-анализ (M2).

**Important:** при цикле `topological_order` выбрасывает `ValueError` — маршрут не должен
строиться на некорректном графе.

#### `backend/app/ontology/seed.py`

**Role:** DOMAIN (сид онтологии)

**Responsibility:** `seed_ontology(session)` — идемпотентная синхронизация онтологии в БД:
темы создаются/обновляются по ключу, рёбра синхронизируются точно (только между
засеянными темами), автосозданные темы не трогаются. CLI: `uv run python -m app.ontology.seed`.

**Depends on:** `backend/app/models/topic.py`, `backend/app/ontology/topics.py`,
`backend/app/db/session.py`.

**Used by:** `backend/README.md`, тесты `backend/tests/test_ontology_seed.py`.

**Important:** повторный запуск не меняет количество строк — сид можно гонять в контейнере
и в тестах.

#### `backend/app/services/analysis.py`

**Role:** SERVICE (извлечение навыков)

**Responsibility:** `extract_vacancy_requirements` и `extract_resume_skills` — извлечение
требований вакансии и навыков резюме через структурированный вывод LLM (жёсткая JSON Schema,
совместимая с режимом strict). Значения вне 0..100 обрезаются, навыки без названия
отбрасываются, пустой текст — понятная ошибка.

**Depends on:** `backend/app/llm/base.py`.

**Used by:** агентские tools (спринт C), REST API профиля, `backend/scripts/eval_extraction.py`.

**Important:** сервисный слой не обращается к БД — доступ к данным у агента остаётся
только через инструменты.

#### `backend/app/services/normalization.py`

**Role:** SERVICE (нормализация)

**Responsibility:** сопоставление навыка с темой онтологии в четыре шага: `exact` → `alias` →
нечёткое совпадение (SequenceMatcher) → косинусная близость (`embedding`). Нормализация
имени учитывает регистр, пунктуацию и кириллические омоглифы («ООП» = «OOP»).
`TopicMatch` фиксирует тему, способ и оценку совпадения.

**Depends on:** `backend/app/embeddings/base.py`.

**Used by:** `backend/app/services/topics.py`, агентские tools, API профиля.

**Important:** несопоставленный навык не отбрасывается — `resolve_or_create_topics()`
создаёт для него provisional-тему и запись в очереди ревью в той же транзакции.

#### `backend/app/services/topics.py`

**Role:** SERVICE (доступ к онтологии)

**Responsibility:** `load_topic_index` — индекс canonical/provisional-тем и алиасов
из БД; `load_packaged_topic_index` — индекс из пакета онтологии с детерминированными
id (тесты и офлайн-режим); `create_skill_matcher` — сборка сопоставителя с порогами
из настроек; `resolve_or_create_topics` — инвариант «у навыка всегда есть `topic_id`»
через provisional-темы, `TopicAlias` и `topic_candidates`.

**Depends on:** `backend/app/models/topic.py`, `backend/app/ontology/topics.py`,
`backend/app/services/normalization.py`.

**Used by:** сервис анализа, агентские tools.

#### `backend/app/services/ontology_review.py`

**Role:** SERVICE (ревью онтологии)

**Responsibility:** `list_review_topics`, `approve_topic`, `reject_topic`,
`merge_topics`. Merge переносит навыки документов, `user_skill_states`, алиасы,
кандидатов и рёбра `REQUIRES`; действия пишутся в `ontology_review_actions`.
Reject разрешён только для темы без ссылок из документов.

**Used by:** CLI `backend/app/ontology/review.py`.

#### `backend/app/services/evaluation.py`

**Role:** SERVICE (метрики качества)

**Responsibility:** precision / recall / F1 по нормализованным названиям навыков —
единая метрика для тестов и для eval-скрипта.

**Depends on:** `backend/app/services/normalization.py`.

#### `backend/app/embeddings/base.py`, `local.py`, `mock.py`, `factory.py`

**Role:** SERVICE (эмбеддинги)

**Responsibility:** `EmbeddingProvider` (протокол) и реализации: `LocalEmbeddingProvider` —
локальная ONNX-модель через fastembed (без внешних сервисов, кэш в
`EMBEDDING_CACHE_DIR`), `MockEmbeddingProvider` — детерминированный для тестов,
`NullEmbeddingProvider` — заглушка; `create_embedding_provider` — выбор по настройкам.
`cosine_similarity` — косинусная близость.

**Depends on:** `backend/app/core/config.py`; `fastembed` — опциональная экстра-группа
(`uv sync --extra embeddings`).

**Used by:** `backend/app/services/normalization.py`.

**Important:** без `fastembed` провайдер сообщает `available = False`, и нормализация
продолжает работать по алиасам и нечёткому совпадению.

#### `backend/scripts/eval_extraction.py`

**Role:** TOOL (eval)

**Responsibility:** прогоняет golden-набор через живой LLM-провайдер, печатает precision /
recall / F1 и точность сопоставления с темами; `--min-f1` задаёт порог, при котором
скрипт завершается с ошибкой.

**Depends on:** `backend/app/services/analysis.py`, `backend/app/services/evaluation.py`,
`backend/tests/fixtures/extraction_golden.py`.

**Used by:** разработчики (нужен `LLM_PROVIDER=openai` с ключом DeepSeek).

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
    ├── app/api/routes/vacancies.py ──┐
    ├── app/api/routes/resumes.py ────┼──▶ app/services/profile.py ──▶ app/services/analysis.py ──▶ LLMProvider
    ├── app/api/routes/profile.py ────┤                              ──▶ app/services/topics.py ──▶ онтология
    ├── app/api/routes/analysis.py ───┘                              ──▶ app/models/* (vacancies, resumes, user_skill_states)
    │        └──▶ app/api/mappers.py ──▶ app/schemas/analysis.py
    │
    └── app/api/deps.py ──▶ app/llm/factory.py ──▶ MockProvider / OpenAIProvider (DeepSeek/OpenAI)

app/agent/analysis_tools.py ──▶ app/services/{analysis,profile}.py (tools привязаны к user_id)

app/agent/deep_harness.py ──▶ deepagents.create_deep_agent ──▶ ProviderChatModel (наш LLMProvider)
app/agent/deep_harness.py ──▶ middleware.py (AuditMiddleware ──▶ audit.py ──▶ agent_actions;
                                             LimitsMiddleware — шаги/токены)
app/agent/deep_harness.py ──▶ langchain_tools.py ──▶ tools.py (JSON Schema + валидация)

app/ontology/seed.py ──▶ app/ontology/topics.py (онтология v2)
                     ──▶ app/ontology/graph.py (проверки графа зависимостей)
                     ──▶ app/models/topic.py ──▶ topics, topic_prerequisites, topic_candidates
app/ontology/graph.py ──▶ только стандартная библиотека (не зависит от ORM)

app/services/analysis.py ──▶ app/llm/base.py (структурированный вывод)
app/services/normalization.py ──▶ app/embeddings/base.py (косинусная близость)
app/services/topics.py ──▶ app/models/topic.py + app/ontology/topics.py (индекс тем)
app/embeddings/factory.py ──▶ app/embeddings/{local,mock}.py; local ──▶ fastembed (экстра-группа)
app/embeddings/local.py ──▶ только стандартная библиотека + fastembed (опционально)

app/models/* ──▶ Base.metadata
alembic/env.py ──▶ config (settings) + Base.metadata ──▶ миграции в БД

tests/* ──▶ app.main (TestClient / AsyncClient); /health/db — через dependency_overrides;
            test_user_model.py и test_auth.py ──▶ реальная БД (skip, если недоступна);
            test_llm.py ──▶ MockProvider (без сети), внешний API — skip без ключа
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

`Base.metadata` содержит модели `User`, `AgentAction` и модели графа знаний
(`Topic`, `TopicPrerequisite`, `TopicCandidate`, `Vacancy`, `VacancySkill`, `Resume`,
`ResumeSkill`, `UserSkillState`); `app/models/__init__.py` импортирует все модели,
поэтому autogenerate видит полные метаданные. Остальные таблицы
([`AGENTS.md`](../AGENTS.md) §5) — по плану вех M3+.

Текущие инфраструктурные связи:

```text
infra/.env ──(подстановка ${...})──▶ infra/docker-compose.yml
                                        ├──(запускает)──▶ контейнер agenthr-postgres
                                        │                        │ named volume postgres_data
                                        └──(собирает backend/Dockerfile)──▶ контейнер agenthr-api
                                                                                 │
                                                              DATABASE_URL ──▶ postgres:5432 (внутри сети)

Backend подключается к БД по `localhost:${POSTGRES_PORT}` (порт на хосте, по умолчанию `5433`) —
при локальном запуске; в контейнере `api` — по имени сервиса `postgres:5432` внутри compose-сети.
API доступен снаружи по `localhost:${API_PORT}` (по умолчанию `8000`).

**План** ([`AGENTS.md`](../AGENTS.md) §2): `Frontend → Backend API → Agent Harness → Tools →
БД / граф знаний / vector store`. Прямой доступ LLM к данным запрещён — только через Tools (§2.3).
Подробная схема — в [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 6. Точки входа

| Точка входа | Файл | Статус |
|---|---|---|
| Запуск инфраструктуры и API | `infra/docker-compose.yml` (сервисы `postgres`, `api`) | реализовано |
| Backend-приложение (локально) | `backend/app/main.py` (uvicorn) | каркас, auth, Agent Harness и доменные API реализованы |
| Backend-приложение (контейнер) | `backend/docker/entrypoint.sh` → uvicorn | миграции + API, healthy |
| Миграции БД | `backend/alembic/` (`uv run alembic ...`) | 9 миграций: pgvector, users, agent_actions, граф знаний, provisional-темы, backfill + `NOT NULL`, аудит ревью, группы требований, критичность |
| Сид онтологии | `backend/app/ontology/seed.py` (`uv run python -m app.ontology.seed`) | 89 canonical-тем, 75 рёбер `REQUIRES`, 233 алиаса, идемпотентно |
| Ревью онтологии | `backend/app/ontology/review.py` (`uv run python -m app.ontology.review ...`) | list / approve / reject / merge + аудит |
| Eval качества извлечения | `backend/scripts/eval_extraction.py` | golden-набор из 5 кейсов; требует живого LLM |
| Прогон тестов backend | `backend/tests/` (pytest) | 158 тестов, 3 пропускаются без флагов живого LLM/эмбеддингов |
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
| `API_PORT` | порт API-контейнера на хосте (по умолчанию `8000`) | нет |
| `JWT_SECRET_KEY` | секрет JWT для контейнера API (пусто → dev-дефолт кода) | да |
| `LLM_PROVIDER` | провайдер LLM в контейнере: `mock` (по умолчанию) или `openai` (DeepSeek) | нет |
| `OPENAI_API_KEY` | ключ DeepSeek (или другого OpenAI-совместимого API) для контейнера API | да |
| `OPENAI_MODEL` | модель API для контейнера API (`deepseek-flash`) | нет |
| `OPENAI_BASE_URL` | базовый URL OpenAI-совместимого API (`https://api.deepseek.com`) | нет |
| `LLM_STRUCTURED_MODE` | режим structured output: `json_schema`, `json_object` (DeepSeek), `prompt` | нет |
| `CORS_ORIGINS` | браузерные источники (JSON-массив) для контейнера API | нет |

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
| `OPENAI_API_KEY` | ключ DeepSeek (или другого OpenAI-совместимого API; нужен для `LLM_PROVIDER=openai`) | да |
| `OPENAI_MODEL` | модель API (нужна для `LLM_PROVIDER=openai`; для DeepSeek — `deepseek-flash`) | нет |
| `OPENAI_BASE_URL` | базовый URL OpenAI-совместимого API (для DeepSeek — `https://api.deepseek.com`) | нет |
| `LLM_STRUCTURED_MODE` | режим structured output: `json_schema`, `json_object` (DeepSeek), `prompt` | нет |
| `OPENAI_TIMEOUT_SECONDS` | таймаут одного запроса к LLM, сек (по умолчанию 30) | нет |
| `OPENAI_MAX_RETRIES` | повторы SDK (по умолчанию 0; резервный запрос делает сам провайдер) | нет |
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

`Dockerfile` frontend и CI-конфигурация — появятся вместе с кодом (`backend/Dockerfile` уже есть).

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

**Факт (дополнение, спринт C):** доменные таблицы используются API — вакансии и резюме
с навыками, срез `user_skill_states` обновляется при загрузке резюме и ручной оценке;
навыки вне онтологии попадают в `topic_candidates` (upsert по `normalized_name`).

**План** ([`AGENTS.md`](../AGENTS.md) §4–5):

- Остальные таблицы схемы: `interview_sessions` / `interview_turns`,
  `learning_plans` / `plan_items`, `embeddings` (pgvector).
- ORM-модели (SQLAlchemy 2) — от `Base` в `backend/app/db/base.py`; миграции — autogenerate.
- Граф знаний на MVP — реляционная модель в Postgres, доступ через репозиторий-границу.

---

## 9. Внешние интеграции

**Факт:** слой LLM реализован: провайдер-агностичный интерфейс, `MockProvider`
(по умолчанию, без сети) и `OpenAIProvider` на официальном SDK; живые вызовы выполняются
при `LLM_PROVIDER=openai` с ключом и моделью. Основной провайдер — DeepSeek
(`OPENAI_BASE_URL=https://api.deepseek.com`, `OPENAI_MODEL=deepseek-flash`,
`LLM_STRUCTURED_MODE=json_object`). Модель вызывается из HTTP-контура при загрузке вакансии
и резюме; `POST /analysis` работает без LLM. При недоступности модели API отвечает 502,
причина пишется в лог. Frontend и backend связаны по REST (CORS для dev-сервера).

**План** ([`AGENTS.md`](../AGENTS.md) §6): использование LLM в продукте — через Agent Harness
(LLM выбирает инструменты, Harness их исполняет и пишет audit-лог). Данные в LLM: тексты
заданий/ответов, структурированный JSON (tool-calls, оценки).

---

## 10. Тесты

**Backend.** `backend/tests/` — 142 теста на pytest (+ `pytest-asyncio`; 139 passed,
3 skipped без `fastembed` и ключа LLM):

- `test_health.py` — `/health` (200 + статус) и `/docs` (200);
- `test_health_db.py` — `/health/db`: 200 и 503 (два случая: `SQLAlchemyError`, `OSError`)
  через подмену зависимости `get_db`; реальная БД не требуется;
- `test_user_model.py` — интеграционный: вставка/чтение `User` в реальной БД; пропускается
  без PostgreSQL;
- `test_auth.py` — интеграционные тесты auth (register/login/me/refresh + негативные кейсы)
  через `httpx2.AsyncClient` + `ASGITransport`;
- `test_cors.py` — CORS-заголовки и preflight для frontend-origin;
- `test_llm.py` — MockProvider и фабрика без сети; режимы structured output; живой тест внешнего API пропускается без ключа;
- `test_agent_tools.py` — реестр инструментов и адаптер для LangChain: дубликаты имён, `specs()`,
  валидация аргументов, дословная JSON Schema, исполнение обработчика, ошибки и таймаут (без БД);
- `test_agent_deep_harness.py` — основной harness (Deep Agents) на мок-LLM: полный цикл
  с инструментом и аудитом, передача JSON Schema, лимиты шагов/токенов, таймаут, ошибки LLM
  и инструмента, продолжение истории по `thread_id`;
- `test_agent_audit.py` — запись/чтение аудит-лога в реальной БД; пропускается без PostgreSQL;
- `test_analysis_api.py` — доменные эндпоинты (вакансии, резюме, профиль, `/analysis`),
  изоляция по пользователю, коды 401/404/422/502; LLM подменена заглушкой;
- `test_analysis_tools.py` — 7 инструментов агента: схемы, валидация, изоляция по владельцу,
  чтение профиля и графа, обновление оценки;
- `test_profile_service.py` — взвешенное слияние оценок, потолок уверенности, приоритет
  источников, ошибка на неизвестной теме;
- `test_e2e_scenario.py` — сквозной сценарий M2 на уровне API: вакансия → резюме → профиль →
  разрывы → `/analysis` → новая вакансия с переиспользованием профиля;
- `test_analysis.py`, `test_normalization.py`, `test_extraction_golden.py`, `test_embeddings*.py` —
  извлечение, нормализация и golden-набор (без сети).

Запуск: `uv run pytest` из `backend/`. Конфигурация — в `backend/pyproject.toml`
(`testpaths`, `pythonpath`, `asyncio_mode`).

**Frontend.** Автотестов нет; проверки — `npm run build` (типы + сборка) и `npm run lint`
(oxlint). Сценарии входа и M2 (регистрация → загрузка вакансии и резюме → анализ → профиль →
пустой профиль) проверены вручную в браузере на dev-сервере.

**План** ([`AGENTS.md`](../AGENTS.md) §9): функциональные тесты, агентские (на мок-LLM),
сценарные e2e, тесты адаптивности, eval-наборы качества LLM.

---

## 11. Скрипты

- **Backend:** каталога `scripts/` и `Makefile` нет; команды — в
  [`backend/README.md`](../backend/README.md) (`uv sync`, `uv run uvicorn`, `uv run pytest`,
  `uv run ruff`, `uv run alembic upgrade head`).
- **Frontend:** npm-скрипты в `frontend/package.json` — `dev`, `build` (`tsc -b && vite build`),
  `lint` (oxlint), `preview`, `generate:api` (типы из OpenAPI, нужен запущенный backend).
- **Инфраструктура:** команды `docker compose` из [`infra/README.md`](../infra/README.md)
  (подъём БД и API — `docker compose up -d`, пересборка образа API — `docker compose up -d --build`).

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
