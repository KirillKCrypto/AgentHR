# PROJECT_MAP — карта репозитория AgentHR

> Навигация: [`AGENTS.md`](../AGENTS.md) → [`ARCHITECTURE.md`](ARCHITECTURE.md) →
> **PROJECT_MAP.md** (этот файл). Детали архитектуры — в `ARCHITECTURE.md`,
> онтологии — в [`ONTOLOGY.md`](ONTOLOGY.md).

## 1. Корень

| Путь | Роль |
|---|---|
| `backend/` | FastAPI, Agent Harness, tools, БД, онтология, тесты |
| `frontend/` | React SPA: экраны, API-клиент, UI |
| `infra/` | Docker Compose: PostgreSQL + pgvector и API |
| `docs/` | архитектура, карта, онтология, roadmap, решения, глоссарий |
| `AGENTS.md` | краткая точка входа для агентов |
| `README.md` | краткое описание для человека |
| `INDEX.md` | карта документации |

## 2. Backend

```text
backend/
├── app/
│   ├── main.py                 FastAPI: CORS, роутеры, /health, /health/db
│   ├── agent/                  Deep Agents, tools, audit, лимиты
│   ├── api/
│   │   ├── deps.py             auth, LLM, embedder
│   │   ├── mappers.py          доменные объекты → Pydantic
│   │   └── routes/             auth, users, vacancies, resumes, profile, analysis
│   ├── core/                   config, JWT/пароли
│   ├── db/                     async engine, Base
│   ├── embeddings/             none/local/mock эмбеддинги
│   ├── llm/                    base, mock, openai (DeepSeek/OpenAI-совместимый), factory
│   ├── models/                 User, AgentAction, Topic, Vacancy, Resume, ...
│   ├── ontology/               topics.py, seed.py, graph.py, review.py
│   ├── schemas/                Pydantic-схемы API
│   └── services/               analysis, normalization, profile, topics,
│                               ontology_review, ontology_auto_review
├── alembic/versions/           миграции
├── docker/entrypoint.sh        миграции + uvicorn
├── Dockerfile
├── tests/
└── pyproject.toml
```

### Где что искать

| Задача | Файлы |
|---|---|
| Извлечение вакансии/резюме | `app/services/analysis.py` |
| Нормализация навыков | `app/services/normalization.py` |
| Онтология и сид | `app/ontology/topics.py`, `seed.py` |
| Provisional-темы / resolver | `app/services/topics.py` |
| Ручное ревью | `app/services/ontology_review.py`, `app/ontology/review.py` |
| Автоматическое ревью | `app/services/ontology_auto_review.py` |
| Профиль и gap-анализ | `app/services/profile.py` |
| REST API | `app/api/routes/` |
| Agent Harness и tools | `app/agent/` |
| ORM-модели | `app/models/` |
| Схемы ответов | `app/schemas/analysis.py`, `auth.py` |
| Настройки | `app/core/config.py`, `.env.example` |

## 3. Frontend

```text
frontend/src/
├── App.tsx                     шапка и маршруты
├── api/
│   ├── client.ts               типизированный API-клиент
│   └── schema.d.ts             генерация из OpenAPI (не редактировать)
├── components/ui/              shadcn/ui
├── lib/                        токены, auth-hook, ошибки, labels
└── pages/                      Dashboard, Login, VacancyUpload, Profile, 404
```

Экраны: `/`, `/login`, `/vacancies/new`, `/profile`.
Планируются: `/plans/:id`, `/interview/:id`, `/reports/:id`.

## 4. Инфраструктура

```text
infra/
├── docker-compose.yml          postgres + api
├── .env.example                шаблон окружения
└── README.md                   запуск, БД, диагностика
```

- API: `http://127.0.0.1:8000`
- PostgreSQL: `localhost:5433`
- UI (Vite): `http://127.0.0.1:5173`

## 5. Миграции

Порядок:

1. `6d7c8a1b787e` — pgvector
2. `68cf3aa5da9d` — users
3. `22cd6bbf10ed` — agent_actions
4. `40b5a867f0dc` — граф знаний и документы
5. `b7e4c2a91f30` — provisional-темы и алиасы
6. `c9a1d2e3f4b5` — backfill `topic_id`, `NOT NULL`, `RESTRICT`
7. `d1e2f3a4b5c6` — аудит ревью онтологии
8. `e2f3a4b5c6d7` — группы требований `AND/OR`
9. `f3a4b5c6d7e8` — критичность `must_have` / `nice_to_have`
10. `a4b5c6d7e8f9` — поля автоматического ревью тем

Новое состояние — только через новую миграцию.

## 6. Точки входа

| Задача | Команда |
|---|---|
| Инфраструктура и API | `docker compose -f infra/docker-compose.yml up -d` |
| Backend локально | `cd backend && uv run uvicorn app.main:app --reload` |
| Frontend | `cd frontend && npm.cmd run dev` |
| Миграции | `cd backend && uv run alembic upgrade head` |
| Сид онтологии | `cd backend && uv run python -m app.ontology.seed` |
| Ревью онтологии | `cd backend && uv run python -m app.ontology.review list` |
| Авто-ревью | `cd backend && uv run python -m app.ontology.review auto` |
| Тесты | `cd backend && uv run pytest -q` |
| Frontend build | `cd frontend && npm.cmd run build` |

## 7. Generated / не редактировать

- `frontend/src/api/schema.d.ts` — генерируется `npm run generate:api`.
- `frontend/package-lock.json`, `backend/uv.lock` — фиксируют зависимости.
- `frontend/dist/`, `.venv/`, `node_modules/`, кэши — не коммитить.
