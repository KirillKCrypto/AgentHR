# ARCHITECTURE — AgentHR

> Навигация: [`INDEX.md`](../INDEX.md) → [`PROJECT_MAP.md`](PROJECT_MAP.md) → **ARCHITECTURE.md** (этот файл).
> Составлено по состоянию на 27.09.2026.
>
> Документ описывает систему на двух уровнях: **Факт** — что реально реализовано в репозитории;
> **План** — что зафиксировано в [`AGENTS.md`](../AGENTS.md), но кода ещё нет. Не смешивай уровни.

---

## 1. Обзор архитектуры

M0 «Фундамент» (неделя 1) и M1 «Agent Harness» (неделя 2) закрыты: реализованы инфраструктура
(PostgreSQL 16 + pgvector в Docker Compose), backend (FastAPI: health, JWT-аутентификация,
слой LLM, Agent Harness на Deep Agents — реестр Tools, middleware аудита и лимитов, checkpointer,
аудит в `agent_actions`; миграции, тесты) и frontend (SPA со входом и регистрацией через API).
Для живого ответа LLM нужен ключ OpenAI; доменные модели данных и внешние интеграции
в рантайме — в плане (дальше — M2: вакансии/резюме → профиль знаний).

Целевая архитектура — агентская система (не чат-бот): `LLM + Agent Harness + Tool Calling +
граф знаний + персистентная память + адаптивное обучение` ([`AGENTS.md`](../AGENTS.md) §1–2).

Далее каждый раздел разделён на «Факт» и «План».

---

## 2. Контекст системы

**Факт.** Система сейчас = контейнер базы данных, backend-сервер и SPA на машине разработчика.
Пользователь открывает SPA, регистрируется или входит (JWT), видит свой профиль на дашборде.
Backend подключён к БД (asyncpg), хранит таблицу `users`, имеет готовый слой LLM (по умолчанию
mock). CORS разрешает запросы с dev-сервера frontend.

**План.** Пользователь проходит сценарий из 7 шагов: загрузка вакансии → загрузка резюме →
анализ уровня → персональный план подготовки → тренировочные интервью → анализ ошибок →
продолжение с накопленной памятью ([`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md) §1).

---

## 3. Высокоуровневая архитектура

### 3.1 Факт (реализовано)

```text
Машина разработчика
   ├── docker compose up -d (infra/) ──▶ agenthr-postgres (pgvector/pgvector:pg16)
   │                                         │ named volume
   │                                         ▼
   │                                     postgres_data (данные переживают перезапуск)
   │                                         ▲
   │                                         │ asyncpg
   ├── docker compose up -d (infra/) ──▶ agenthr-api (образ из backend/Dockerfile) ──▶ FastAPI (backend/app)
   │        (альтернатива: uv run uvicorn app.main:app в backend/ — локальный запуск)
   │                                                 - entrypoint контейнера: alembic upgrade head → uvicorn
   │                                                 - GET /health, /health/db
   │                                                 - POST /auth/register, /auth/login, /auth/refresh
   │                                                 - GET /me (Bearer access)
   │                                                 - CORS: http://localhost:5173
   │                                                 - слой LLM: MockProvider / OpenAIProvider (app/llm/)
   │                                                 - Agent Harness: Deep Agents + middleware аудита/лимитов (app/agent/)
   │                                                 - модели User, AgentAction, Topic, Vacancy, Resume, UserSkillState (app/models/)
   │                                                 - Alembic-миграции (pgvector, users, agent_actions, граф знаний и документы)
   │                                                 - онтология v2: 89 тем, 75 пререквизитов, идемпотентный сид (app/ontology/)
   └── npm run dev (frontend/) ──▶ Vite dev-сервер (SPA)
                                     - /login: регистрация и вход через REST API
                                     - /: дашборд — /me через TanStack Query, выход
                                     - токены (access/refresh) в localStorage
                                     │
                                     └── REST (fetch) ──▶ Backend API
```

### 3.2 План (не реализовано)

Схема зафиксирована в [`AGENTS.md`](../AGENTS.md) §2.1:

```text
Frontend (React SPA)
    │ REST + WebSocket
Backend API (FastAPI)          ← auth, бизнес-логика, владелец БД, запуск сессий
    │
    ├── Agent Harness (Deep Agents) ──► LLM Agent
    │        │ Tool Calls                 │
    │        ▼                            │
    │   Tools (реестр) ◄──────────────────┘   ← только tools трогают данные
    │
    ├── Knowledge Graph (Postgres: topics + prerequisites + user_skill_states)
    ├── Vector Store (pgvector)
    └── Database (PostgreSQL: сессии, ответы, оценки, audit-лог)
```

---

## 4. Компоненты

### Инфраструктура (Факт)

**Location:** `infra/`

**Ответственность:** предоставить локальные БД и API для разработки.

**Основные компоненты:** `docker-compose.yml` (сервисы `postgres` и `api`), `.env.example` /
`.env` (параметры подключения и настройки API), `README.md` (инструкции); образ API собирается
из `backend/Dockerfile`.

**Зависимости:** Docker Desktop; `backend/Dockerfile` для сервиса `api`; внешних сервисов нет.

**Потребители:** разработчики; backend (в контейнере — через `postgres:5432`, локально —
через `localhost:${POSTGRES_PORT}`); frontend (API по `localhost:${API_PORT}`).

**Ограничения:** данные в named volume; удаление — только `docker compose down -v`; порт на хосте
по умолчанию `5433` (5432 часто занят локальным PostgreSQL) и может конфликтовать с другими
проектами Docker; образ API пересобирается после изменения кода (`up -d --build`).

### Backend (каркас, auth, слой LLM и Agent Harness реализованы)

**Location:** `backend/`

**Реализовано:** FastAPI-точка входа `app/main.py` (health-эндпоинты, CORS, подключение
роутеров, обработчик `LLMError` → 502), JWT-аутентификация (`app/api/`: `register`, `login`,
`refresh`, `/me`; `app/core/security.py`: argon2id + PyJWT), слой LLM (`app/llm/`:
провайдер-агностичный интерфейс `LLMProvider`, `MockProvider` для тестов без сети,
`OpenAIProvider` — function calling и структурированный вывод по JSON Schema с резервным
режимом «схема в промпте»; фабрика по `LLM_PROVIDER`), доменные REST-эндпоинты
(`/vacancies`, `/resumes`, `/profile`, `/profile/gaps`, `/analysis`), сервисный слой
(`app/services/`: извлечение, нормализация, профиль знаний и gap-анализ), настройки
`app/core/config.py` (pydantic-settings), слой БД `app/db/` (async-движок, фабрика сессий,
`get_db`, `Base`), модели графа знаний и документов (`app/models/`), схемы (`app/schemas/`),
миграции Alembic (`alembic/`), тесты `tests/`; контейнеризация — `backend/Dockerfile` и
`backend/docker/entrypoint.sh` (миграции применяются при старте контейнера).

**Ответственность по плану:** остальные модели и схема БД, доменные REST API, сервисный слой,
запуск агентских сессий, трансляция стрима; владелец БД ([`AGENTS.md`](../AGENTS.md) §2.2).

**Стек:** Python 3.13, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, PyJWT, pwdlib (argon2),
openai, Deep Agents (LangGraph + LangChain core); образ — `python:3.13-slim` + uv.

### Frontend (экраны M2 реализованы)

**Location:** `frontend/`

**Реализовано:** SPA на Vite + React 19 + TypeScript; Tailwind CSS 4; shadcn/ui (Base UI);
роутинг react-router 8 (`/` — дашборд, `/login` — вход/регистрация, `/vacancies/new` —
загрузка вакансии и резюме, `/profile` — профиль знаний, 404); TanStack Query; типизированный
API-клиент `src/api/client.ts` (типы из OpenAPI — `src/api/schema.d.ts`, генерация
`npm run generate:api`); хранение токенов (`src/lib/tokens.ts`, localStorage) и сброс сессии
при 401 (`src/lib/useAuthToken.ts`); экран `/login` с регистрацией и понятными ошибками;
дашборд с `/me`, списком вакансий, переходами к подготовке/профилю и выходом; экран
`/vacancies/new` с последовательностью «вакансия → резюме → анализ» и выводом навыков,
готовности и разрывов; `/profile` с темами 0–100, источником и уверенностью, подсветкой
пробелов по выбранной вакансии и блоком навыков вне онтологии; состояния
loading/error/empty/ready; зафиксированные версии зависимостей; линтер oxlint.

**Ответственность по плану:** остальные экраны — план подготовки (`/plans/:id`), интервью
с WebSocket-стримингом (`/interview/:id`), отчёт (`/reports/:id`)
([`AGENTS.md`](../AGENTS.md) §7).

**Ограничения:** без state-менеджеров (TanStack Query + `useState`), без анимаций и кастомных
визуализаций; UI — только shadcn/ui; версии зависимостей фиксированы.

### Agent Harness и Tools (реализовано)

**Реализовано:** реестр Tools с JSON Schema и валидацией (`app/agent/tools.py`); основной цикл
агента — на **Deep Agents** (`app/agent/deep_harness.py`: `create_deep_agent` поверх LangGraph,
checkpointer `InMemorySaver` по `thread_id`, статусы `completed` / `max_steps` / `token_budget` /
`timeout` / `llm_error`); наши правила встроены middleware (`app/agent/middleware.py`):

- `AuditMiddleware` — каждый вызов модели (шаг, токены) и каждый вызов инструмента (аргументы,
  результат, длительность, статус) пишется в `agent_actions` (`app/agent/audit.py`);
- `LimitsMiddleware` — остановка цикла по числу шагов (`AGENT_MAX_STEPS`) и бюджету токенов
  (`AGENT_TOKEN_BUDGET`) с понятным сообщением; таймаут прогона — `AGENT_TIMEOUT_SECONDS`;
- ошибка инструмента (валидация, таймаут, исключение обработчика) возвращается модели как
  `ToolMessage(status="error")` — цикл не прерывается.

Инструменты реестра попадают в агент через адаптер `app/agent/langchain_tools.py` (JSON Schema
передаётся модели дословно), а наш провайдер-агностичный слой LLM — через `app/agent/langchain_model.py`
(`BaseChatModel` поверх `LLMProvider`, включая `MockProvider` в тестах). Контракт результата прогона —
`app/agent/result.py`.

**Ограничение:** checkpointer пока в памяти — при рестарте процесса состояние потоков теряется
(PostgreSQL-checkpointer — отдельный шаг). Агент работает с дефолтным составом Deep Agents:
файловая система (управление контекстом) и сабагент `task` включены (решение команды от окт. 2026).

Целевая роль: harness — состояние, маршрутизация tool-calls, лимиты, audit-лог;
Tools — типизированные функции, единственный способ агента дотянуться до данных
([`AGENTS.md`](../AGENTS.md) §2.2, §3.2–3.3). Слой LLM готов (`app/llm/`).

### Граф знаний и векторный слой (частично реализовано)

**Факт:** созданы таблицы `topics` (ключ, название, описание, алиасы, версия онтологии,
флаг автосозданной темы), `topic_prerequisites` (ребро `REQUIRES`), `topic_candidates`
(навыки вне онтологии — пул тем на ревью) и `user_skill_states` (срез профиля по
паре «пользователь × тема»). Онтология v2 — 89 атомарных тем и 75 рёбер `REQUIRES`,
сид идемпотентен (`app/ontology/`); состав и ограничения — в [`ONTOLOGY.md`](ONTOLOGY.md). Слой эмбеддингов (`app/embeddings/`): локальная ONNX-модель
(multilingual MiniLM, 384 измерения) без внешних сервисов, с деградацией к alias и
нечёткому совпадению, если пакет не установлен.

Профиль знаний материализуется в `user_skill_states`: оценки объединяются взвешенно по
источнику (`manual` > `interview` > `assessment` > `resume`), уверенность считается по
независимым свидетельствам и ограничена `0.95`. Gap-анализ (`compute_gaps`) считает разрывы
«требуется − есть»; `coverage_all` включает provisional-темы, `confirmed_readiness` —
только canonical. Непроверенные темы помечаются `status` / `topic_status`, а навыки вне
словаря показываются отдельно (`unmatched_count`).

**План:** таблица `embeddings` — на неделе 7 ([`AGENTS.md`](../AGENTS.md) §4); планировщик
маршрута по графу и адаптация интервью — M3–M4.

---

## 5. Потоки данных

**Факт:** поток A (onboarding) реализован по M2: загрузка вакансии → `extract_vacancy_requirements`
(структурированный вывод LLM) → нормализация к онтологии (`exact → alias → fuzzy → embedding`)
→ запись `vacancies` / `vacancy_skills`; загрузка резюме → `extract_resume_skills` → запись
`resumes` / `resume_skills` → пересборка профиля (`user_skill_states`); gap-анализ считает
разрывы и готовность к вакансии. Навыки вне онтологии сохраняются с `topic_id = NULL` и
попадают в `topic_candidates`. Golden-набор и eval-скрипт меряют качество извлечения.
Поток аутентификации: регистрация → argon2-хеш → `users`; логин → проверка хеша → пара
JWT-токенов в SPA; дашборд → `GET /me` с access-токеном.

**План** ([`AGENTS.md`](../AGENTS.md) §2.4):

- **A. Onboarding:** расширение онтологии по кандидатам и ревью новых тем — по мере накопления данных.
- **B. Планирование:** «требуется вакансией − текущий уровень» → gap-анализ → приоритизированный
  план (gap-анализ готов, план — M3).
- **C. Интервью (реалтайм):** генерация вопроса → ответ → `evaluate_answer` → обновление графа →
  `adjust_difficulty` → следующий вопрос → `save_interview_result` + отчёт.
- **D. Память:** старт с `load_user_profile`; накопленный профиль переиспользуется между вакансиями
  (профиль и инструмент `get_user_skill_state` готовы, агентский цикл — M3–M4).

---

## 6. Поток запроса

**Backend** — маршруты в `backend/app/api/routes/` и `backend/app/main.py`:

- `GET /health` — статус и окружение (без обращения к БД);
- `GET /health/db` — `SELECT 1` через `get_db`: 200 / 503;
- `POST /auth/register` — валидация → argon2-хеш → `INSERT` (409 при занятом email);
- `POST /auth/login` — проверка пароля (401 при ошибке) → пара access/refresh-токенов;
- `POST /auth/refresh` — проверка refresh-токена → новая пара;
- `GET /me` — `get_current_user`: Bearer → проверка access-JWT → `SELECT` пользователя → 200/401;
- `POST /vacancies` — LLM извлекает требования → нормализация к онтологии → запись
  `vacancies` / `vacancy_skills` → 201; 422 при нечитаемом ответе модели, 502 при недоступной LLM;
- `GET /vacancies`, `GET /vacancies/{id}` — список (без навыков) и карточка с навыками;
- `POST /resumes` — извлечение навыков → запись `resumes` / `resume_skills` → пересборка профиля;
- `GET /resumes`, `GET /resumes/{id}` — список и карточка резюме;
- `GET /profile` — срез `user_skill_states` + навыки вне онтологии;
- `GET /profile/gaps?vacancy_id=...` — разрывы и готовность к вакансии;
- `POST /analysis` — документы, профиль и разрывы одним ответом; LLM не вызывается.

Доменные эндпоинты защищены `get_current_user` и изолированы по владельцу: обращение к чужому
документу возвращает 404. `LLMError` обрабатывается глобально — 502 с понятным текстом,
причина пишется в лог.

**Frontend** — поток входа:

```text
Форма /login
   └── src/api/client.ts ──▶ POST /auth/login (или /auth/register → /auth/login)
          ├── успех ──▶ saveTokens(localStorage) ──▶ редирект на /
          └── ошибка ──▶ ApiError(status) ──▶ сообщение в форме

Дашборд /
   └── useQuery(['me']) ──▶ GET /me (Bearer access)
   └── useQuery(['vacancies']) ──▶ GET /vacancies
          ├── 200 ──▶ «Вы вошли как …» + список вакансий + «Выйти»
          ├── 401 ──▶ очистка токенов ──▶ «Сессия истекла»
          └── нет токена ──▶ «Вы не вошли в аккаунт» + ссылка на /login

Новая подготовка /vacancies/new
   └── POST /vacancies ──▶ POST /resumes ──▶ POST /analysis
          ├── успех ──▶ навыки, готовность и разрывы на экране
          └── ошибка ──▶ сообщение (422/502/сеть), введённые тексты сохранены

Профиль /profile
   └── GET /profile + GET /vacancies ──▶ GET /profile/gaps?vacancy_id=…
          ├── 200 ──▶ темы 0–100, пробелы, навыки вне онтологии
          └── пусто ──▶ «Профиль пока пуст» + ссылка на /vacancies/new
```

**План:** WebSocket для стриминга интервью ([`AGENTS.md`](../AGENTS.md) §2.1, §3.3);
эндпоинты плана подготовки и сессий интервью — M3–M4.

---

## 7. Слой данных

**Факт:**

- СУБД: PostgreSQL 16 в контейнере `agenthr-postgres` (образ `pgvector/pgvector:pg16`).
- Расширение `vector` создаётся миграцией Alembic `6d7c8a1b787e`
  (`CREATE EXTENSION IF NOT EXISTS vector`; откат удаляет расширение).
- Таблица `users` создаётся миграцией `68cf3aa5da9d`: `id` (UUID, `gen_random_uuid()`),
  `email` (уникальный), `password_hash` (argon2id-хеш), `created_at` (`timestamptz`, `now()`).
  ORM-модель — `backend/app/models/user.py`.
- Таблица `agent_actions` (миграция `22cd6bbf10ed`) — аудит-лог действий агента: шаг, tool,
  аргументы/результат (JSONB), статус, токены, длительность; `session_id` без FK (до недели 5).
  ORM-модель — `backend/app/models/agent_action.py`.
- Миграция `40b5a867f0dc` — граф знаний и документы:
  - `topics` — тема онтологии: `key` (уникальный), `name`, `description` (текст для эмбеддингов),
    `category`, `aliases` (JSONB), `ontology_version`, `is_auto_generated`;
  - `topic_prerequisites` — ребро `REQUIRES` (`topic_id` → `prerequisite_id`), запрет саморебра;
  - `topic_candidates` — навык вне онтологии: уникальный `normalized_name`, `occurrences`,
    `sources` (JSONB), `status` (new/approved/rejected/merged);
  - `vacancies` / `vacancy_skills` — вакансия пользователя и её навыки (`required_level` 0–100,
    `weight`, `confidence`, `match_method`; `topic_id` — NULL, если навык не сопоставлен);
  - `resumes` / `resume_skills` — резюме пользователя и его навыки (`proficiency` 0–100,
    `confidence`, `evidence`, `match_method`);
  - `user_skill_states` — срез профиля: уникальная пара `(user_id, topic_id)`, `proficiency` 0–100,
    `confidence`, `source`, `evidence` (JSONB), `last_assessed`.
  ORM-модели — `backend/app/models/topic.py`, `vacancy.py`, `resume.py`, `user_skill_state.py`,
  `ontology_review.py`.
- Миграция `b7e4c2a91f30` — provisional-темы и алиасы:
  - `topics.status` (`canonical`/`provisional`/`merged`/`rejected`), `origin`, `canonical_topic_id`;
  - `topic_aliases` — уникальный `normalized_alias` на всю онтологию;
  - `topic_candidates.topic_id` — provisional-тема, созданная для кандидата.
  Для новых документов `topic_id` у навыков всегда заполнен: `resolve_or_create_topics()`
  создаёт provisional-тему в той же транзакции.
- Миграция `c9a1d2e3f4b5` — backfill и обязательный `topic_id`:
  - исторические NULL-навыки привязываются к темам или получают provisional-темы;
  - `resume_skills.topic_id` / `vacancy_skills.topic_id` — `NOT NULL`;
  - FK темы у навыков — `RESTRICT` вместо `SET NULL`;
  - `AUTO_TOPIC_LIMIT` ограничивает число новых тем на документ, overflow идёт
    в одну review-тему.
- Миграция `d1e2f3a4b5c6` — `ontology_review_actions`:
  - аудит `approve` / `reject` / `merge` с source/target, актором и деталями;
  - ревью выполняется CLI `python -m app.ontology.review`.
- Подключение: `DATABASE_URL` из `backend/.env` (локальный дефолт в `app/core/config.py`);
  движок и сессии — `backend/app/db/session.py` (asyncpg, `pool_pre_ping`).
- Миграции: Alembic (async-шаблон), URL берётся в `alembic/env.py` из настроек;
  команды — `uv run alembic upgrade head` / `downgrade base` / `current`.
  Цикл upgrade → downgrade → upgrade проверен на локальной БД.

**План** ([`AGENTS.md`](../AGENTS.md) §4–5): остальные таблицы схемы (`interview_sessions`,
`interview_turns`, `learning_plans`, `plan_items`, `embeddings` и др.); ORM-модели
SQLAlchemy 2 (async); `agent_actions` — обязательный audit-лог; граф знаний — реляционная
модель в Postgres с репозиторием-границей (без Neo4j в MVP).

---

## 8. Внешние интеграции

**Факт:** слой LLM реализован и по умолчанию использует `MockProvider` (без сети);
`OpenAIProvider` (официальный SDK) активируется настройками и выполняет живые вызовы при
заданных `OPENAI_API_KEY` и `OPENAI_MODEL`; `OPENAI_BASE_URL` позволяет работать через
OpenAI-совместимый шлюз. Загрузка вакансии и резюме вызывает модель из HTTP-контура
(`POST /vacancies`, `POST /resumes`); `POST /analysis` модель не вызывает.
Структурированный вывод сначала использует `response_format=json_schema`, при отказе шлюза
повторяется с описанием схемы в промпте. Ошибки SDK и сети превращаются в `LLMError` → 502.
Frontend и backend связаны по REST (CORS-разрешение для dev-сервера).

**План** ([`AGENTS.md`](../AGENTS.md) §6, §10):

| Параметр | Значение |
|---|---|
| Integration | LLM-провайдер (OpenAI или совместимый шлюз; запасной — Anthropic), провайдер-агностичный слой |
| Purpose | анализ, планирование, генерация вопросов, оценка ответов |
| Location | `backend/app/llm/`; вызовы из сервисного слоя и (далее) из агентского цикла |
| Configuration | `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`, таймауты/повторы |
| Data exchanged | тексты промптов/ответов, структурированный JSON (tool-calls, оценки) |
| Failure handling | таймаут запроса, один резервный запрос без strict-схемы, 502 в API, audit-лог |

---

## 9. Конфигурация

**Факт** — `infra/.env` (копия `infra/.env.example`, в git не попадает):

| Переменная | Назначение | Секрет |
|---|---|---|
| `POSTGRES_USER` | логин суперпользователя контейнера | да |
| `POSTGRES_PASSWORD` | пароль | да |
| `POSTGRES_DB` | имя базы, создаваемой при инициализации | нет |
| `POSTGRES_PORT` | порт БД на хосте (по умолчанию `5433`) | нет |
| `API_PORT` | порт API-контейнера на хосте (по умолчанию `8000`) | нет |
| `JWT_SECRET_KEY` | секрет JWT для контейнера API (пусто → dev-дефолт кода) | да |
| `LLM_PROVIDER` | провайдер LLM в контейнере (`mock` по умолчанию) | нет |
| `OPENAI_API_KEY` | ключ OpenAI (или совместимого шлюза) для контейнера API | да |
| `OPENAI_MODEL` | модель OpenAI для контейнера API | нет |
| `OPENAI_BASE_URL` | базовый URL OpenAI-совместимого шлюза (пусто — `api.openai.com`) | нет |
| `CORS_ORIGINS` | браузерные источники (JSON-массив) для контейнера API | нет |

**Backend** — `backend/.env` (копия `backend/.env.example`):

| Переменная | Назначение | Секрет |
|---|---|---|
| `APP_NAME` | заголовок FastAPI-приложения | нет |
| `ENVIRONMENT` | название окружения (`local`, ...) | нет |
| `DATABASE_URL` | подключение к PostgreSQL (`postgresql+asyncpg://...`) | да (содержит пароль) |
| `JWT_SECRET_KEY` | секрет подписи JWT (dev-дефолт в коде; в проде — только из окружения) | да |
| `JWT_ALGORITHM` | алгоритм подписи (`HS256`) | нет |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | время жизни access-токена (по умолчанию 30) | нет |
| `REFRESH_TOKEN_EXPIRE_DAYS` | время жизни refresh-токена (по умолчанию 30) | нет |
| `LLM_PROVIDER` | провайдер LLM: `mock` (по умолчанию) или `openai` | нет |
| `OPENAI_API_KEY` | ключ OpenAI (или совместимого шлюза) для `LLM_PROVIDER=openai` | да |
| `OPENAI_MODEL` | модель OpenAI (для `LLM_PROVIDER=openai`) | нет |
| `OPENAI_BASE_URL` | базовый URL OpenAI-совместимого шлюза (пусто — `api.openai.com`) | нет |
| `OPENAI_TIMEOUT_SECONDS` | таймаут одного запроса к LLM, сек (по умолчанию 30) | нет |
| `OPENAI_MAX_RETRIES` | повторы SDK при ошибках (по умолчанию 0: резервный запрос делает провайдер) | нет |
| `CORS_ORIGINS` | браузерные источники (по умолчанию `["http://localhost:5173"]`) | нет |
| `AGENT_MAX_STEPS` | максимум шагов агентского цикла (по умолчанию 10) | нет |
| `AGENT_TOKEN_BUDGET` | бюджет токенов на цикл (по умолчанию 50000) | нет |
| `AGENT_TIMEOUT_SECONDS` | общий таймаут цикла, сек (по умолчанию 120) | нет |
| `AGENT_TOOL_TIMEOUT_SECONDS` | таймаут одного инструмента, сек (по умолчанию 30) | нет |

**Frontend** — `frontend/.env.example` (копия в `frontend/.env` при необходимости):

| Переменная | Назначение | Секрет |
|---|---|---|
| `VITE_API_BASE_URL` | базовый URL backend (по умолчанию `http://127.0.0.1:8000`) | нет |

Прочая конфигурация frontend в репозитории: `frontend/package.json`,
`frontend/.npmrc` (`save-exact=true`), `frontend/vite.config.ts` (React + Tailwind 4, alias
`@/*`), `frontend/tsconfig*.json`, `frontend/components.json` (shadcn/ui),
`frontend/.oxlintrc.json`.

Значения переменных окружения в документации не приводятся. `.env.example` — шаблоны для
локальной разработки, они коммитятся. Настройки backend читает `app/core/config.py`
(pydantic-settings).

Прочие конфигурационные файлы: `.editorconfig`, `.gitattributes`, `.gitignore`,
`backend/alembic.ini`, `backend/.python-version` (пин Python 3.13).

---

## 10. Аутентификация / авторизация

**Backend (факт):** JWT (access + refresh), сервер не хранит сессии:

- `POST /auth/register` — argon2id-хеш пароля (`pwdlib`), 409 при занятом email;
- `POST /auth/login` — проверка пароля (одинаковый 401 для неверного пароля и неизвестного
  email; фиктивный хеш выравнивает время ответа), выдача пары токенов (`PyJWT`, HS256;
  claims `sub`/`type`/`iat`/`exp`);
- `POST /auth/refresh` — новая пара по refresh-токену;
- `GET /me` — защищённый эндпоинт (зависимость `get_current_user`, `HTTPBearer`).

Access-TTL — 30 минут, refresh-TTL — 30 дней (настройки). Секрет — `JWT_SECRET_KEY`
(dev-дефолт в коде, в продакшене обязательно переопределить). Refresh-токены stateless.

**Frontend (факт):** экран `/login` вызывает `/auth/register` и `/auth/login`; токены
сохраняются в `localStorage`; доменные экраны (`/vacancies/new`, `/profile`) и дашборд
запрашивают API с `Authorization: Bearer`; при 401 токены очищаются (`useAuthToken`);
«Выйти» очищает токены и состояние. Refresh-механика в UI пока не используется.

**Изоляция доменных данных (факт):** сервисы получают `user_id` из проверенного токена и
проверяют владельца при чтении документа (иначе `NotFoundError` → 404); агентские инструменты
собираются под конкретного пользователя и сессию БД — `user_id` не приходит от модели.

**План** ([`AGENTS.md`](../AGENTS.md) §6, §10): при необходимости отзыва токенов — таблица
refresh-сессий (отдельный шаг); возможен переход на httpOnly-cookie для снижения XSS-риска.

---

## 11. Фоновая обработка

**Факт:** отсутствует (нет воркеров, очередей, jobs).

**План:** в MVP отдельный компонент не выделен; в рисках упомянут «отдельный воркер агента» как
возможное решение для латентности стрима ([`AGENTS.md`](../AGENTS.md) §10).

---

## 12. Обработка ошибок

**Факт:** `/health/db` отвечает 503 при недоступной БД (`SQLAlchemyError`/`OSError`);
auth-эндпоинты — 401 (неверные данные/токен), 409 (дубликат email), 422 (валидация Pydantic);
слой LLM использует исключения `LLMError`/`LLMConfigurationError` (глобальный обработчик — 502).
Frontend: `ApiError` со статусом; на `/login` показываются понятные сообщения (401/409/422/прочее);
на доменных экранах — состояния loading/error/empty/ready, сообщения для 401/422/502,
повтор запроса; при 401 сессия очищается.

**План** ([`AGENTS.md`](../AGENTS.md) §9–10): валидация схем `tool_call`, откат при ошибке
инструмента, лимиты/таймауты, fallback-ответ агента; единый маппинг ошибок в UI.

---

## 13. Тестирование

**Backend (факт):** подключён pytest (+ `pytest-asyncio`); в `backend/tests/` 142 теста
(139 passed, 3 skipped: два теста локального эмбеддера без `fastembed`, живой LLM без ключа):

- `test_health.py` — `/health` и `/docs`;
- `test_health_db.py` — `/health/db`: 200 и 503 (через подмену `get_db`, без реального Postgres);
- `test_user_model.py` — вставка/чтение `User` в реальной БД (пропускается, если БД недоступна);
- `test_auth.py` — register/login/me/refresh и негативные кейсы (дубликат email, неверный пароль,
  отсутствие/битый/просроченный токен, refresh вместо access) через `httpx2.AsyncClient`
  и `ASGITransport`;
- `test_cors.py` — CORS-заголовок и preflight для frontend-origin;
- `test_llm.py` — MockProvider и фабрика без сети; живой вызов OpenAI пропускается без ключа;
- `test_agent_tools.py` — реестр инструментов и адаптер для LangChain: валидация аргументов,
  дословная JSON Schema, исполнение обработчика, ошибки и таймаут (без БД);
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
- `test_e2e_scenario.py` — E2E-скелет M2 на уровне API: вакансия → резюме → профиль →
  разрывы → `/analysis` → новая вакансия с переиспользованием профиля;
- `test_analysis.py`, `test_normalization.py`, `test_extraction_golden.py`, `test_embeddings*.py` —
  извлечение, нормализация и golden-набор (без сети).

Запуск: `uv run pytest` из `backend/`; конфигурация — в `backend/pyproject.toml`.

**Frontend (факт):** автотестов нет; проверки — `npm run build` (типы + production-сборка)
и `npm run lint` (oxlint); сценарии входа и M2 (регистрация → загрузка вакансии и резюме →
анализ → профиль → пустой профиль) проверены вручную в браузере на dev-сервере.

**План** ([`AGENTS.md`](../AGENTS.md) §9): функциональные тесты, агентские (на мок-LLM), сценарные
e2e, тесты адаптивности на синтетических пользователях, eval-наборы для качества LLM (извлечение,
оценка ответов).

---

## 14. Сборка и запуск

**Факт.** Инфраструктура (из [`infra/README.md`](../infra/README.md)): `docker compose up -d`
поднимает БД `agenthr-postgres` и API `agenthr-api` (образ собирается из `backend/Dockerfile`);
entrypoint контейнера сам применяет миграции.

```powershell
cd infra
Copy-Item .env.example .env       # один раз
docker compose up -d              # БД + API (первый раз соберёт образ)
docker compose up -d --build      # после изменений кода backend
docker compose ps                 # статус (healthy)
docker compose logs -f api        # логи API (миграции + uvicorn)
docker compose down               # остановка (данные сохраняются)
docker compose down -v            # остановка + удаление данных
```

Backend (из [`backend/README.md`](../backend/README.md)):

```powershell
cd backend
uv sync                                  # установка зависимостей (Python 3.13)
Copy-Item .env.example .env              # один раз
uv run alembic upgrade head              # миграции (нужна запущенная БД)
uv run uvicorn app.main:app --reload     # запуск сервера (http://127.0.0.1:8000)
uv run pytest                            # тесты
uv run ruff check .                      # линтер
```

Frontend (из [`frontend/README.md`](../frontend/README.md)):

```powershell
cd frontend
npm install
npm run dev              # http://localhost:5173 (нужен запущенный backend)
npm run build            # проверка типов + production-сборка
npm run lint             # oxlint
npm run generate:api     # обновить типы из OpenAPI (нужен запущенный backend)
```

При локальном запуске backend миграции применяются вручную (`alembic upgrade head`);
в контейнере `api` — автоматически на старте. `Dockerfile` backend есть, `Dockerfile` frontend
и CI отсутствуют. Платформа разработки — Windows + Docker Desktop + uv + Node.js.

---

## 15. Архитектурные ограничения

Зафиксированы в [`AGENTS.md`](../AGENTS.md) §2.3, §13 и обязательны к соблюдению:

1. LLM не обращается к БД/графу напрямую — только через Tools.
2. Все действия агента логируются (`agent_actions`, audit-лог).
3. Состояние сессии сохраняется (checkpoint) — сессию можно продолжить/восстановить.
4. Новое состояние — только через миграции Alembic.
5. Каждый инструмент — с JSON Schema, валидацией и записью в audit-лог.
6. Frontend: без state-менеджеров, анимаций и кастомных визуализаций без явного запроса;
   UI — только из shadcn/ui; версии зависимостей зафиксированы; один типизированный API-клиент.
7. Граф знаний на MVP — реляционная модель в Postgres; доступ через репозиторий-границу
   (для возможной миграции на Neo4j/AGE без переписывания агента).
8. Язык: документация и комментарии — русский; коммиты — английский (conventional commits);
   идентификаторы — латиница.

---

## 16. Известные архитектурные риски

- **Порт БД.** 5432 часто занят локальным PostgreSQL; проект использует 5433. При смене порта
  синхронизировать `infra/.env` и `DATABASE_URL` в `backend/.env`.
- **Зависимость от Docker Desktop.** При выключенном движке команды `docker compose` не работают,
  контейнеры `agenthr-postgres` и `agenthr-api` недоступны, а `/health/db` отвечает 503.
- **Конфликт портов с другими проектами.** `5433` (БД) и `8000` (API) — общие для машины;
  другие compose-проекты могут их занимать (встречалось со стеком Airflow). При конфликте
  освободить порт или изменить `POSTGRES_PORT` / `API_PORT` в `infra/.env`.
- **Миграции.** Локальный запуск требует `alembic upgrade head` вручную; в контейнере `api`
  миграции применяются entrypoint'ом на старте (неудачная миграция останавливает контейнер).
- **Аутентификация MVP.** Refresh-токены stateless (отозвать до истечения нельзя); токены
  в `localStorage` (XSS-риск, принятый для MVP); refresh-механика в UI не используется;
  dev-дефолт `JWT_SECRET_KEY` нельзя использовать в продакшене.
- **CORS настроен на dev-origin.** При смене порта frontend-сервера обновить `CORS_ORIGINS`.
- **Генерация типов вручную.** `schema.d.ts` обновляется скриптом при работающем backend;
  при изменении API без регенерации типы разойдутся с backend.
- **LLM по умолчанию — mock.** Реальные вызовы требуют ключа и модели; без ключа живые сценарии
  LLM-слоя не проверяются (тест пропускается).
- **Checkpointer в памяти.** Состояние агентских потоков (`thread_id`) живёт в процессе backend:
  после рестарта сессии не восстановить (PostgreSQL-checkpointer — отдельный шаг).
- **Стадия проекта.** Значительная часть архитектуры существует только в плане; риск расхождения
  документации и кода снижается правилом обновлять эти три документа при изменениях.
- **Плановые риски проекта** (точность оценки ответов, качество онтологии, стоимость agent-loop,
  приватность и др.) перечислены в [`AGENTS.md`](../AGENTS.md) §10 — здесь не дублируются.
