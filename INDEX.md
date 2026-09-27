# INDEX — AgentHR

> Главная точка входа для ИИ-агентов. Составлено по состоянию на 27.09.2026.
>
> Порядок чтения: **INDEX.md** (этот файл) → [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) (где находится код) →
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (как компоненты связаны).
> Контекст, требования и правила проекта — [`AGENTS.md`](AGENTS.md).

---

## 1. Обзор проекта

AgentHR — интеллектуальная агентская система адаптивной подготовки к техническим собеседованиям
под конкретные вакансии. Это не чат-бот: целевая архитектура строится вокруг агентского цикла —
`LLM + Agent Harness (LangGraph) + Tool Calling + граф знаний (Postgres) + персистентная память
(pgvector) + адаптивное обучение`.

- **Тип:** monorepo — `backend/` + `frontend/` + `infra/`.
- **Стек (зафиксирован):** Python 3.13 + FastAPI, LangGraph + LangChain core, PostgreSQL 16 +
  pgvector, React + TypeScript + Vite, Docker Compose, Alembic + SQLAlchemy, pytest.
- **Текущее состояние:** реализованы инфраструктура (Docker Compose с PostgreSQL 16 + pgvector,
  `infra/`), backend (FastAPI: health, JWT-auth, слой LLM, модель `User`, миграции, тесты —
  `backend/`) и каркас frontend (Vite + React 19 + TS, Tailwind CSS 4, shadcn/ui, роутинг,
  страницы-заглушки — `frontend/`). Из чеклиста старта ([`AGENTS.md`](AGENTS.md), §12)
  выполнены пункты 1–3, 5, 6; пункт 4 выполняется поэтапно (миграции, pgvector, `users`;
  остальные таблицы — недели 3–4); пункт 10 — частично (каркас готов; подключение `/login`
  к API — следующий шаг); пункты 7–9, 11 не начаты.

---

## 2. Быстрый старт

Запускаются три компонента: база данных, backend (FastAPI) и frontend (Vite). Требования:
Docker Desktop с запущенным движком и [uv](https://docs.astral.sh/uv/), Node.js 20+.

**1. База данных** (`infra/`):

```powershell
cd infra
Copy-Item .env.example .env   # один раз: локальные креды, в git не попадают
docker compose up -d
docker compose ps             # agenthr-postgres должен перейти в healthy
```

Проверка БД и расширения `vector`, остановка — команды в [`infra/README.md`](infra/README.md).

**2. Backend** (`backend/`):

```powershell
cd backend
uv sync                                       # зависимости (Python 3.13)
Copy-Item .env.example .env                   # один раз: локальные настройки
uv run alembic upgrade head                   # миграции (нужна запущенная БД)
uv run uvicorn app.main:app --reload          # http://127.0.0.1:8000 (+ /docs)
uv run pytest                                 # тесты
```

По умолчанию `LLM_PROVIDER=mock` — сеть не нужна. Для реального вызова задайте
`LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL` в `backend/.env`.

**3. Frontend** (`frontend/`):

```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173
```

---

## 3. Структура репозитория

```text
AgentHR/
├── AGENTS.md            — контекст проекта, план, правила (главный проектный документ)
├── README.md            — краткое описание проекта и стека
├── INDEX.md             — этот файл: точка входа для ИИ-агентов
├── docs/                — навигационная документация
│   ├── PROJECT_MAP.md   — карта каталогов и файлов
│   └── ARCHITECTURE.md  — архитектура и связи компонентов
├── infra/               — РЕАЛИЗОВАНО: PostgreSQL 16 + pgvector в Docker Compose
│   ├── docker-compose.yml
│   ├── .env.example     — шаблон окружения (.env — локальный, в git не попадает)
│   └── README.md        — запуск и проверка БД
├── backend/             — КАРКАС: FastAPI, JWT-auth, слой LLM, модель User, БД-сессия, Alembic
│   ├── app/
│   │   ├── main.py      — точка входа FastAPI (подключение роутеров, /health, /health/db)
│   │   ├── api/         — роутеры (routes/auth.py, routes/users.py), deps.py (get_current_user)
│   │   ├── core/        — config.py (настройки), security.py (argon2-хеши, JWT)
│   │   ├── db/          — async-движок (session.py), Base (base.py)
│   │   ├── llm/         — провайдер-агностичный слой LLM (base, mock, openai, factory)
│   │   ├── models/      — ORM-модели (user.py — User)
│   │   └── schemas/     — Pydantic-схемы (auth.py)
│   ├── alembic/         — миграции (async; pgvector, users)
│   ├── alembic.ini      — конфигурация Alembic
│   ├── tests/           — тесты (pytest)
│   ├── pyproject.toml   — зависимости и конфигурация инструментов (uv)
│   ├── uv.lock          — зафиксированные версии (генерируется, коммитится)
│   ├── .env.example     — шаблон настроек (.env — локальный, в git не попадает)
│   └── README.md        — команды запуска, тестов, миграций
└── frontend/            — КАРКАС: Vite + React 19 + TS, Tailwind 4, shadcn/ui, роутинг; заглушки
    ├── src/
    │   ├── main.tsx     — точка входа (QueryClientProvider, BrowserRouter)
    │   ├── App.tsx      — шапка и маршруты /, /login, 404
    │   ├── pages/       — экраны (DashboardPage, LoginPage, NotFoundPage)
    │   ├── components/ui/ — shadcn/ui (Button, Card, Input, Label)
    │   └── lib/utils.ts — утилита cn
    ├── index.html
    ├── package.json     — зависимости (зафиксированные версии)
    ├── package-lock.json
    └── README.md        — команды и соглашения
```

---

## 4. Основные компоненты

### Инфраструктура — реализовано

**Path:** `infra/`

Локальная база данных для всей разработки: PostgreSQL 16 с расширением pgvector, healthcheck,
именованный volume. Параметры подключения — через `infra/.env` (порт на хосте по умолчанию `5433`).

Подробнее: [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) → раздел `infra/`;
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) → «Слой данных».

### Backend — каркас реализован

**Path:** `backend/`

Реализовано: FastAPI-приложение — health-эндпоинты (`/health`, `/health/db`), JWT-аутентификация
(`POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET /me`; argon2-хеши паролей
в `app/core/security.py`), слой LLM (`app/llm/`: провайдер-агностичный интерфейс, `MockProvider`
для тестов без сети, `OpenAIProvider` на официальном SDK — function calling и JSON Schema),
настройки через pydantic-settings (`app/core/config.py`), слой БД (async-движок и сессии
SQLAlchemy в `app/db/`), модель `User` (`app/models/`), миграции Alembic (pgvector, таблица
`users`), тесты (`tests/`), зависимости через uv (`pyproject.toml`, `uv.lock`).

По плану здесь появятся: остальные модели и схема БД, доменные REST API (вакансии, резюме,
планы, интервью), Agent Harness (LangGraph), реестр Tools. Источник: [`AGENTS.md`](AGENTS.md)
§2–3, §6.

Подробнее: [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) → раздел `backend/`.

### Frontend — каркас реализован

**Path:** `frontend/`

Реализовано: каркас SPA — Vite + React 19 + TypeScript, Tailwind CSS 4, shadcn/ui (Base UI),
роутинг (react-router 8), TanStack Query (настроен), страницы-заглушки: дашборд (`/`), вход
(`/login` — форма без подключения к API), 404. Версии зависимостей зафиксированы
(`.npmrc` → `save-exact=true`).

По плану: подключение экрана входа к API (следующий шаг), затем остальные экраны
(`/vacancies/new`, `/profile`, `/plans/:id`, `/interview/:id`, `/reports/:id`).
Источник: [`AGENTS.md`](AGENTS.md) §7.

Подробнее: [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) → раздел `frontend/`;
[`frontend/README.md`](frontend/README.md) — команды и соглашения.

### Документация и управление

**Path:** `README.md`, `AGENTS.md`, `INDEX.md`, `docs/`

Описание проекта, требования/правила и навигация по репозиторию.

---

## 5. Обзор архитектуры

**Фактически сейчас** (работающие контуры):

```text
Машина разработчика
   ├── docker compose up -d (infra/) ──▶ agenthr-postgres (PostgreSQL 16 + pgvector)
   │                                         │ named volume postgres_data
   │                                         ▼ данные переживают перезапуск
   ├── uv run uvicorn app.main:app (backend/) ──▶ FastAPI (backend/app)
   │                                                 - GET /health, /health/db
   │                                                 - POST /auth/register, /auth/login, /auth/refresh
   │                                                 - GET /me (Bearer access-токен)
   │                                                 - слой LLM: MockProvider / OpenAIProvider
   │                                                 - модель User (app/models/)
   │                                                 - Alembic-миграции (pgvector, users)
   └── npm run dev (frontend/) ──▶ Vite dev-сервер (SPA-каркас)
                                     - / (дашборд-заглушка), /login (форма без API), 404
                                     - пока не обращается к backend (следующий шаг)
```

Backend подключается к БД по `localhost:5433` (asyncpg; пароли — argon2id-хеши, токены — JWT).
LLM по умолчанию — mock (сеть не нужна); OpenAI включается настройками.

**Целевая архитектура (план, не реализована)** — [`AGENTS.md`](AGENTS.md) §2:

```text
Frontend (React SPA)
      │ REST + WebSocket
Backend API (FastAPI)
      │
      ├── Agent Harness (LangGraph) ──► LLM Agent
      │        │ Tool Calls
      │        ▼
      │   Tools (реестр)  ← единственный способ агента дотянуться до данных
      ├── Knowledge Graph (Postgres)
      ├── Vector Store (pgvector)
      └── Database (PostgreSQL)
```

Полное описание факта и плана — [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 6. Точки входа

| Точка входа | Роль | Статус |
|---|---|---|
| `infra/docker-compose.yml` | запуск БД и инфраструктуры | реализовано |
| `backend/app/main.py` (запуск: `uvicorn app.main:app`) | основной сервер приложения | каркас + auth реализованы |
| `backend/alembic/` (запуск: `uv run alembic upgrade head`) | миграции схемы БД | 2 миграции: pgvector, users |
| Тесты: `backend/tests/` (`uv run pytest`) | прогон тестов | 28 тестов (1 пропускается без ключа OpenAI) |
| `frontend/` (запуск: `npm run dev`) | SPA-разработка | каркас (страницы-заглушки) |

---

## 7. Важные файлы

| Файл | Роль |
|---|---|
| `AGENTS.md` | требования, план на 8 недель, архитектурные правила, глоссарий — главный источник истины по замыслу |
| `README.md` | краткое описание проекта и стека |
| `backend/app/main.py` | точка входа FastAPI: роутеры auth/users, `/health`, `/health/db` |
| `backend/app/core/config.py` | настройки приложения (pydantic-settings) |
| `backend/app/core/security.py` | argon2-хеширование паролей, выпуск/проверка JWT |
| `backend/app/api/routes/auth.py` | `register`, `login`, `refresh` |
| `backend/app/api/deps.py` | `get_current_user` (Bearer-защита эндпоинтов) |
| `backend/app/db/session.py` | async-движок, фабрика сессий, зависимость `get_db` |
| `backend/app/models/user.py` | ORM-модель `User` |
| `backend/app/llm/` | слой LLM: интерфейс (`base.py`), `MockProvider`, `OpenAIProvider`, фабрика |
| `backend/alembic/` | миграции схемы (async) |
| `backend/pyproject.toml` | зависимости, конфигурация pytest и ruff |
| `frontend/src/App.tsx` | маршруты и шапка SPA |
| `frontend/src/pages/` | экраны (пока заглушки) |
| `frontend/src/components/ui/` | компоненты shadcn/ui (Button, Card, Input, Label) |
| `frontend/package.json` | зависимости frontend (зафиксированные версии) |
| `infra/docker-compose.yml` | описание контейнера с БД |
| `infra/.env.example` | шаблон локального окружения (креды, порт) |
| `infra/README.md` | команды запуска/проверки/остановки БД |
| `.gitignore` | исключения git (`.env`, `.venv`, `node_modules` и др.) |
| `backend/README.md`, `frontend/README.md` | README подсистем |

---

## 8. Карта документации

```text
INDEX.md                    — главная точка входа (этот файл)
├── docs/PROJECT_MAP.md     — где находятся каталоги и файлы, за что отвечают
├── docs/ARCHITECTURE.md    — как компоненты связаны между собой, потоки данных
├── AGENTS.md               — исходные требования, план, архитектурные правила
├── README.md               — краткое описание проекта
├── infra/README.md         — работа с локальной БД
├── backend/README.md       — работа с backend (запуск, тесты, миграции)
└── frontend/README.md      — работа с frontend (запуск, сборка, соглашения)
```

---

## 9. Критические области

- **`AGENTS.md`** — источник правил и плана. При изменениях проверять согласованность
  `INDEX.md` / `docs/PROJECT_MAP.md` / `docs/ARCHITECTURE.md` и что план не выдан за факт.
- **`infra/docker-compose.yml`** — от него зависит БД всей команды. Изменение порта, volume или
  healthcheck затрагивает: `infra/.env`, `infra/README.md`, настройки backend (`DATABASE_URL`).
- **`backend/app/core/config.py`** — настройки backend. При добавлении переменных обновлять
  `backend/.env.example`; секреты — только через локальный `.env`.
- **`backend/app/core/security.py`** — хеширование и токены. Смена формата claims/TTL затрагивает
  всех клиентов; `JWT_SECRET_KEY` в продакшене меняется только вместе с инвалидацией токенов.
- **`backend/app/llm/base.py`** — контракт слоя LLM (сообщения, tools, результаты). Изменение
  контракта затронет всех провайдеров и будущий Agent Harness.
- **`backend/app/models/`** — ORM-модели: изменение модели требует новой миграции
  (`alembic revision --autogenerate`).
- **`backend/alembic/versions/`** — уже применённые миграции не редактировать; новые — только
  через `alembic revision`. Состояние БД воспроизводится командами `upgrade head` / `downgrade base`.
- **`frontend/src/components/ui/`** — сгенерированные компоненты shadcn/ui; правки вносить
  осознанно (обновление реестром перезапишет). Новые компоненты — `npx shadcn@latest add <name>`.
- **`frontend/package.json`** — версии зафиксированы (`.npmrc` → `save-exact=true`); не добавлять
  state-менеджеры и анимации без явной необходимости ([`AGENTS.md`](AGENTS.md) §7, §13).
- **`infra/.env` и `backend/.env`** — локальные файлы; в git не коммитятся, значения
  не документируются.
- **Порт БД** — на хосте по умолчанию `5433` (5432 часто занят локальным PostgreSQL); при смене
  синхронизировать `infra/.env` и `DATABASE_URL` в `backend/.env`.

---

## 10. Generated / Do Not Edit

- `backend/uv.lock` — генерируется uv; коммитится; вручную не редактируется.
- `backend/alembic/versions/*` — файлы миграций (генерируются `alembic revision`); коммитятся.
  Содержимое новой миграции можно дополнять руками, **применённые** ревизии не редактируются.
- `frontend/src/components/ui/*` — генерируются shadcn CLI (правки только осознанно).
- `frontend/package-lock.json` — генерируется npm; коммитится; вручную не редактируется.
- `frontend/node_modules/`, `frontend/dist/` — локальные/артефакты сборки; игнорируются
  (`frontend/.gitignore`).
- `infra/.env` и `backend/.env` — локальные файлы, не коммитить; значения не включать
  в документацию.
- Локальные/игнорируемые (`backend/.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`,
  `*.log`) перечислены в `.gitignore`.

---

## 11. AI Agent Rules

1. Перед изменением кода определи подсистему и её ответственность по этому файлу и
   [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md).
2. Не придумывай несуществующие модули: в `backend/` есть каркас (`app/main.py`, `app/api/`,
   `app/core/`, `app/db/`, `app/llm/`, `app/models/` — только `User`, `app/schemas/`, `alembic/`,
   `tests/`), во `frontend/` — каркас (3 страницы-заглушки, 4 компонента UI); доменных роутеров
   и сервисов пока нет. Перед созданием файла проверь, что его ещё нет.
3. Соблюдай архитектурные правила проекта ([`AGENTS.md`](AGENTS.md) §2.3, §13): LLM не обращается
   к БД/графу напрямую — только через Tools; все действия агента логируются; состояние сессии
   сохраняется (checkpoint).
4. Новое состояние БД — только через миграции Alembic.
5. Не трогай секреты: `infra/.env` и `backend/.env` не коммитить, значения не документировать.
6. Фича считается готовой только при наличии теста и прогона реального сценария
   ([`AGENTS.md`](AGENTS.md) §13).
7. При изменении структуры проекта обновляй `docs/PROJECT_MAP.md`; при изменении архитектурных
   связей — `docs/ARCHITECTURE.md`; при существенных изменениях — `INDEX.md`.
8. Язык: документация и комментарии — русский; коммиты — английский (conventional commits);
   идентификаторы — латиница ([`AGENTS.md`](AGENTS.md) §13).
9. Не выдавай план за факт. Всё, что ещё не реализовано, помечай как «план (AGENTS.md)» — так же,
   как это сделано в этих трёх документах.

---

## 12. Быстрая навигация (Quick Navigation)

| Вопрос | Ответ |
|---|---|
| Где инфраструктура / запуск БД? | `infra/` → [`infra/README.md`](infra/README.md) |
| Где API? | Роутеры — `backend/app/api/routes/` (auth, users); health — `backend/app/main.py`; остальное — план ([`AGENTS.md`](AGENTS.md) §2–3) |
| Где аутентификация? | `backend/app/core/security.py` (argon2 + JWT), `backend/app/api/deps.py` (`get_current_user`) |
| Где LLM-слой? | `backend/app/llm/` (`base.py` — интерфейс, `mock.py` / `openai.py` — реализации, `factory.py` — выбор по `LLM_PROVIDER`) |
| Где фронтенд? | `frontend/` (каркас: маршруты — `src/App.tsx`, экраны — `src/pages/`, запуск — `npm run dev`) |
| Где UI-компоненты? | `frontend/src/components/ui/` (shadcn/ui, Base UI); новые — `npx shadcn@latest add <name>` |
| Где агент, Harness и Tools? | Пока нет; план — `backend/` ([`AGENTS.md`](AGENTS.md) §3) |
| Где работа с БД (модели, сессии, миграции)? | Модели — `backend/app/models/`; сессии — `backend/app/db/`; миграции — `backend/alembic/` |
| Где конфигурация окружения? | `backend/.env.example` (backend, включая JWT и LLM), `infra/.env.example` (БД) |
| Где тесты? | `backend/tests/` → `uv run pytest`; frontend — `npm run build` + `npm run lint` ([`AGENTS.md`](AGENTS.md) §9 — план расширения) |
| Где правила разработки? | [`AGENTS.md`](AGENTS.md) §13 |
| Где план на 8 недель? | [`AGENTS.md`](AGENTS.md) §8 |
| Где подробная карта файлов? | [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) |
| Где описание архитектуры? | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
