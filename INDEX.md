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
  `infra/`) и скелет backend (FastAPI + `/health`, настройки через pydantic-settings, тесты —
  `backend/`). `frontend/` — пока README-заглушка. Из чеклиста старта ([`AGENTS.md`](AGENTS.md), §12)
  выполнены пункты 1–3; пункты 4–11 не начаты.

---

## 2. Быстрый старт

Запускаются два компонента: база данных и backend (FastAPI). Требования: Docker Desktop
с запущенным движком и [uv](https://docs.astral.sh/uv/).

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
uv run uvicorn app.main:app --reload          # http://127.0.0.1:8000 (+ /docs)
uv run pytest                                 # тесты
```

Команды frontend появятся вместе с кодом.

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
├── backend/             — СКЕЛЕТ: FastAPI (/health, настройки, тесты); Agent Harness и tools — план
│   ├── app/
│   │   ├── main.py      — точка входа FastAPI, эндпоинт /health
│   │   └── core/config.py — настройки (pydantic-settings)
│   ├── tests/           — тесты (pytest)
│   ├── pyproject.toml   — зависимости и конфигурация инструментов (uv)
│   ├── uv.lock          — зафиксированные версии (генерируется, коммитится)
│   ├── .env.example     — шаблон настроек (.env — локальный, в git не попадает)
│   └── README.md        — команды запуска, тестов и линтера
└── frontend/            — ПЛАН: React SPA; сейчас только README.md
```

---

## 4. Основные компоненты

### Инфраструктура — реализовано

**Path:** `infra/`

Локальная база данных для всей разработки: PostgreSQL 16 с расширением pgvector, healthcheck,
именованный volume. Параметры подключения — через `infra/.env` (порт на хосте по умолчанию `5433`).

Подробнее: [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) → раздел `infra/`;
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) → «Слой данных».

### Backend — скелет реализован

**Path:** `backend/`

Реализовано: каркас FastAPI-приложения — точка входа `app/main.py`, эндпоинт `/health`, настройки
через pydantic-settings (`app/core/config.py`), тесты (`tests/`), зависимости и инструменты
через uv (`pyproject.toml`, `uv.lock`).

По плану здесь появятся: REST API (auth, вакансии, резюме, планы, интервью), Agent Harness
(LangGraph), реестр Tools, слой БД (SQLAlchemy + Alembic), JWT-auth, провайдер-агностичный
слой LLM. Источник: [`AGENTS.md`](AGENTS.md) §2–3, §6.

Подробнее: [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) → раздел `backend/`.

### Frontend — план (кода нет)

**Path:** `frontend/` — пока только `README.md`.

По плану: React SPA, 7 экранов (`/login`, дашборд, загрузка вакансии, профиль, план, интервью,
отчёт). Источник: [`AGENTS.md`](AGENTS.md) §7.

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
   └── uv run uvicorn app.main:app (backend/) ──▶ FastAPI-скелет: GET /health, /docs
```

Backend и БД пока не связаны (подключение — следующий шаг плана).

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
| `backend/app/main.py` (запуск: `uvicorn app.main:app`) | основной сервер приложения | скелет реализован |
| Тесты: `backend/tests/` (`uv run pytest`) | прогон тестов | базовые тесты есть |
| Точка входа frontend (Vite) | SPA | не создана (`frontend/` — заглушка) |

---

## 7. Важные файлы

| Файл | Роль |
|---|---|
| `AGENTS.md` | требования, план на 8 недель, архитектурные правила, глоссарий — главный источник истины по замыслу |
| `README.md` | краткое описание проекта и стека |
| `backend/app/main.py` | точка входа FastAPI, эндпоинт `/health` |
| `backend/app/core/config.py` | настройки приложения (pydantic-settings) |
| `backend/pyproject.toml` | зависимости, конфигурация pytest и ruff |
| `infra/docker-compose.yml` | описание контейнера с БД |
| `infra/.env.example` | шаблон локального окружения (креды, порт) |
| `infra/README.md` | команды запуска/проверки/остановки БД |
| `.gitignore` | исключения git (`.env`, `.venv`, `node_modules` и др.) |
| `backend/README.md`, `frontend/README.md` | README подсистем (frontend — заглушка) |

---

## 8. Карта документации

```text
INDEX.md                    — главная точка входа (этот файл)
├── docs/PROJECT_MAP.md     — где находятся каталоги и файлы, за что отвечают
├── docs/ARCHITECTURE.md    — как компоненты связаны между собой, потоки данных
├── AGENTS.md               — исходные требования, план, архитектурные правила
├── README.md               — краткое описание проекта
├── infra/README.md         — работа с локальной БД
└── backend/README.md       — работа с backend (запуск, тесты)
```

---

## 9. Критические области

- **`AGENTS.md`** — источник правил и плана. При изменениях проверять согласованность
  `INDEX.md` / `docs/PROJECT_MAP.md` / `docs/ARCHITECTURE.md` и что план не выдан за факт.
- **`infra/docker-compose.yml`** — от него зависит БД всей команды. Изменение порта, volume или
  healthcheck затрагивает: `infra/.env`, `infra/README.md`, будущие настройки backend.
- **`backend/app/core/config.py`** — настройки backend. При добавлении переменных обновлять
  `backend/.env.example`; секреты — только через локальный `.env`.
- **`infra/.env`** — локальный файл с кредами; в git не коммитится, значения не документируются.
- **Порт БД** — на хосте по умолчанию `5433` (5432 часто занят локальным PostgreSQL); при смене
  синхронизировать `.env` и будущую конфигурацию backend.

---

## 10. Generated / Do Not Edit

Автогенерируемые артефакты сейчас: `backend/uv.lock` (создаётся uv, коммитится, вручную
не редактируется). Правила:

- `infra/.env` и `backend/.env` — локальные файлы, не коммитить; значения не включать
  в документацию.
- Локальные/игнорируемые (`backend/.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`,
  `node_modules/`, `dist/`, `*.log`) перечислены в `.gitignore`.
- Когда появятся Alembic-миграции: уже применённые ревизии вручную не редактировать.

---

## 11. AI Agent Rules

1. Перед изменением кода определи подсистему и её ответственность по этому файлу и
   [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md).
2. Не придумывай несуществующие модули: в `backend/` есть только скелет (`app/main.py`,
   `app/core/config.py`, `tests/`), `frontend/` пока пуст. Перед созданием файла проверь,
   что его ещё нет.
3. Соблюдай архитектурные правила проекта ([`AGENTS.md`](AGENTS.md) §2.3, §13): LLM не обращается
   к БД/графу напрямую — только через Tools; все действия агента логируются; состояние сессии
   сохраняется (checkpoint).
4. Новое состояние БД — только через миграции Alembic (когда backend подключится к БД).
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
| Где API? | `backend/app/main.py` (сейчас только `/health`); остальное — план ([`AGENTS.md`](AGENTS.md) §2–3) |
| Где агент, Harness и Tools? | Пока нет; план — `backend/` ([`AGENTS.md`](AGENTS.md) §3) |
| Где фронтенд? | Пока нет; план — `frontend/` ([`AGENTS.md`](AGENTS.md) §7) |
| Где работа с БД (модели, миграции)? | Пока нет; реализована только сама БД — `infra/` |
| Где конфигурация окружения? | `backend/.env.example` (backend), `infra/.env.example` (БД) |
| Где тесты? | `backend/tests/` → `uv run pytest` ([`AGENTS.md`](AGENTS.md) §9 — план расширения) |
| Где правила разработки? | [`AGENTS.md`](AGENTS.md) §13 |
| Где план на 8 недель? | [`AGENTS.md`](AGENTS.md) §8 |
| Где подробная карта файлов? | [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) |
| Где описание архитектуры? | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
