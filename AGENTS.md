# AGENTS.md — AgentHR

> Точка входа для ИИ-агентов. Здесь только краткий контекст, стек, запуск и правила.
> Подробности — в файлах из раздела «Документация».

---

## 1. Что это за проект

AgentHR — интеллектуальная агентская система адаптивной подготовки к техническим
собеседованиям под конкретную вакансию.

Это не чат-бот. Ключевая идея:

```text
LLM + Agent Harness + Tool Calling + Knowledge Graph + Persistent Memory + Adaptive Learning
```

Пользователь загружает вакансию и резюме, получает профиль знаний, gap-анализ,
персональный план подготовки и тренировочные интервью с адаптацией сложности.
Память переиспользуется между вакансиями.

## 2. Текущий статус

- **M0–M2 закрыты:** инфраструктура, auth, Deep Agents, извлечение навыков,
  нормализация, профиль знаний, gap-анализ.
- **Онтология:** этапы 1–4 закрыты — 89 canonical-тем, provisional-темы,
  backfill, CLI ревью, автоматическое ревью, `coverage_all` / `confirmed_readiness`,
  группы `AND/OR`, `criticality`.
- **Следующий этап онтологии:** `evidence_type` / `verified_level`.
- **Следующая веха продукта:** M3 — план подготовки и сессия интервью.

Подробный статус и план: [`docs/ONTOLOGY.md`](docs/ONTOLOGY.md),
[`docs/ROADMAP.md`](docs/ROADMAP.md).

## 3. Технологический стек

| Слой | Технология |
|---|---|
| Backend | Python 3.13, FastAPI |
| Agent Harness | Deep Agents (LangGraph + LangChain core) |
| LLM | DeepSeek (`deepseek-flash`, `json_object`); OpenAI-совместимый слой, запасной — OpenAI/Anthropic |
| Database | PostgreSQL 16 |
| Vector store | pgvector |
| Knowledge Graph | реляционная модель в Postgres |
| Frontend | React 19, TypeScript, Vite |
| UI | Tailwind CSS 4, shadcn/ui |
| Client state | TanStack Query + `useState`, без Redux/Zustand |
| Real-time | WebSocket |
| Auth | JWT (access + refresh) |
| Миграции | Alembic + SQLAlchemy 2 (async) |
| Инфраструктура | Docker Compose |
| Тесты | pytest, httpx, ruff |

Отложено: Neo4j/AGE, RAG, визуализация графа, второй LLM-провайдер,
spaced repetition, мультиагентность, голос/таймеры, предиктор готовности.

## 4. Структура репозитория

```text
AgentHR/
├── backend/       FastAPI, Agent Harness, tools, БД, онтология, тесты
├── frontend/      React SPA (Vite)
├── infra/         Docker Compose: PostgreSQL + pgvector и API
├── docs/          архитектура, карта кода, онтология, roadmap, решения
├── AGENTS.md      этот файл
└── README.md      краткое описание для человека
```

## 5. Быстрый старт

Требования: Docker Desktop с запущенным engine, [uv](https://docs.astral.sh/uv/),
Node.js 20+.

### 5.1. БД и API в Docker

```powershell
cd infra
Copy-Item .env.example .env      # один раз
docker compose up -d             # postgres + api
docker compose ps                # оба контейнера healthy
```

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- PostgreSQL: `localhost:5433`
- после изменения backend: `docker compose up -d --build`

### 5.2. Backend локально

```powershell
cd backend
uv sync
Copy-Item .env.example .env      # один раз
uv run alembic upgrade head      # нужна запущенная БД
uv run uvicorn app.main:app --reload
```

### 5.3. Frontend

```powershell
cd frontend
npm.cmd install                  # npm.cmd — если PowerShell блокирует npm.ps1
npm.cmd run dev                  # http://127.0.0.1:5173
```

## 6. Команды проверки

```powershell
# backend
cd backend
uv run pytest -q
uv run ruff check .
uv run alembic current
uv run alembic check

# frontend
cd frontend
npm.cmd run build
npm.cmd run lint
npm.cmd run generate:api         # нужен запущенный API
```

Онтология:

```powershell
cd backend
uv run python -m app.ontology.seed
uv run python -m app.ontology.review list
uv run python -m app.ontology.review auto
```

## 7. Правила работы агента

- **LLM не обращается к БД напрямую** — только через tools.
- Каждый tool имеет JSON Schema, валидацию и запись в audit-лог.
- Новое состояние БД — только через миграции Alembic.
- Фича готова только с тестом и прогоном реального сценария.
- Frontend: без state-менеджеров, анимаций и кастомных визуализаций без запроса.
- При неоднозначности — предложить варианты с компромиссами, не выбирать молча.
- Язык общения, документации и комментариев — русский; коммиты — conventional commits
  на английском; идентификаторы — латиницей.
- Секреты хранить только в локальных `.env`; не коммитить и не печатать ключи.
- Перед push показать сообщение коммита и предложить as-is или squash.

## 8. Документация

| Файл | Что внутри | Когда читать |
|---|---|---|
| [`README.md`](README.md) | краткое описание и быстрый старт | первый вход в проект |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | архитектура, компоненты, потоки данных, модель данных | перед изменением архитектуры |
| [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) | карта модулей и файлов, миграции, точки входа | перед поиском кода |
| [`docs/ONTOLOGY.md`](docs/ONTOLOGY.md) | онтология, provisional-темы, gap-анализ, план этапов | при работе с навыками и оценкой |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | вехи, 8-недельный план, экраны, тестирование, риски | при планировании |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | зафиксированные решения и компромиссы | перед спорным выбором |
| [`docs/GLOSSARY.md`](docs/GLOSSARY.md) | термины проекта | при незнакомом термине |
| [`backend/README.md`](backend/README.md) | backend: API, LLM, tools, тесты | при работе с backend |
| [`frontend/README.md`](frontend/README.md) | frontend: экраны, API-клиент, сборка | при работе с UI |
| [`infra/README.md`](infra/README.md) | Docker Compose, БД, диагностика | при проблемах с окружением |
