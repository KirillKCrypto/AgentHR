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
| `backend/` | APPLICATION (План) | будущий backend: FastAPI, Agent Harness, Tools; сейчас README-заглушка |
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
│   └── README.md
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

**Используется:** разработчиками (команды `docker compose`); в будущем — backend при подключении
к БД (`localhost:${POSTGRES_PORT}`).

**Важно:** данные хранятся в named volume `agenthr_postgres_data`; удаляются только
`docker compose down -v`.

### `backend/` — План

**Role:** APPLICATION (backend)

**Цель по плану:** FastAPI-приложение, Agent Harness (LangGraph), реестр Tools, слой БД
(SQLAlchemy 2 async + Alembic), JWT-auth, провайдер-агностичный слой LLM.
Источники: `backend/README.md`, [`AGENTS.md`](../AGENTS.md) §2–3, §6.

**Сейчас содержит:** только `README.md`. Кода нет.

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

**Used by:** локальный запуск БД для всей команды; будущий backend (подключение к БД).

**Important:** изменение порта/volume/healthcheck затрагивает `infra/.env`, `infra/README.md`
и будущую конфигурацию backend. `docker compose down -v` удаляет данные.

#### `infra/.env.example`

**Role:** CONFIG (шаблон)

**Responsibility:** шаблон локального окружения: `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`, `POSTGRES_PORT`. Копируется в `infra/.env`.

**Depends on:** —

**Used by:** `docker compose` (значения для контейнера), `infra/README.md`.

**Important:** реальный `.env` не коммитится (см. `.gitignore`). Значения из файла в документации
не приводятся (кроме дефолтов шаблона, предназначенного для локальной разработки).

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

### Уровень 3 — вспомогательные

| Файл | Роль | Назначение |
|---|---|---|
| `.gitignore` | CONFIG | исключения: Python-кэши, `.venv`, `node_modules`, `dist`, `.env` (кроме `.env.example`), IDE, OS |
| `.editorconfig` | CONFIG | UTF-8, LF; Python — 4 пробела, TS/JS/JSON/YAML/CSS/HTML — 2 пробела |
| `.gitattributes` | CONFIG | `* text=auto eol=lf`; CRLF для `.bat`/`.ps1` |
| `backend/README.md` | DOCUMENTATION | заглушка: состав будущего backend и стек |
| `frontend/README.md` | DOCUMENTATION | заглушка: состав будущего frontend и стек |
| `docs/PROJECT_MAP.md` | DOCUMENTATION | этот файл |
| `docs/ARCHITECTURE.md` | DOCUMENTATION | архитектура: факт и план |

---

## 5. Зависимости между модулями

**Факт.** Кода приложения нет, поэтому зависимостей между модулями нет. Существуют только связи
инфраструктуры:

```text
infra/.env ──(подстановка ${...})──▶ infra/docker-compose.yml ──(запускает)──▶ контейнер agenthr-postgres
                                                                                       │
                                                                             named volume postgres_data
```

Будущий backend подключится к БД по адресу `localhost:${POSTGRES_PORT}` (порт на хосте,
по умолчанию `5433`).

**План** ([`AGENTS.md`](../AGENTS.md) §2): `Frontend → Backend API → Agent Harness → Tools →
БД / граф знаний / vector store`. Прямой доступ LLM к данным запрещён — только через Tools (§2.3).
Подробная схема — в [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 6. Точки входа

| Точка входа | Файл | Статус |
|---|---|---|
| Запуск инфраструктуры | `infra/docker-compose.yml` | реализовано |
| Backend-приложение | — | нет (план: `backend/`) |
| Frontend-приложение | — | нет (план: `frontend/`) |
| Прогон тестов | — | нет (план: pytest, [`AGENTS.md`](../AGENTS.md) §9) |

---

## 7. Конфигурационные файлы

### `infra/.env.example` (и локальный `infra/.env`)

| Переменная | Назначение | Секрет |
|---|---|---|
| `POSTGRES_USER` | логин суперпользователя контейнера | да |
| `POSTGRES_PASSWORD` | пароль | да |
| `POSTGRES_DB` | имя базы, создаваемой при инициализации | нет |
| `POSTGRES_PORT` | порт БД на хосте (по умолчанию `5433`; 5432 часто занят локальным PostgreSQL) | нет |

### Прочие конфигурационные файлы

- `.editorconfig` — единый стиль форматирования.
- `.gitattributes` — нормализация переводов строк.
- `.gitignore` — исключения git.

### Отсутствуют (План)

`pyproject.toml`, `package.json`, `alembic.ini`, `Dockerfile` приложений, CI-конфигурация —
появятся вместе с кодом.

---

## 8. Компоненты БД

**Факт:**

- СУБД: PostgreSQL 16 в контейнере `agenthr-postgres` (образ `pgvector/pgvector:pg16`).
- Расширение `vector` доступно в образе; проверка — команда в [`infra/README.md`](../infra/README.md).
  В текущем локальном контейнере расширение уже установлено; на чистой БД его нужно создать
  (`CREATE EXTENSION IF NOT EXISTS vector`), по плану это будет делать первая миграция Alembic.
- Подключение: `localhost`, порт `POSTGRES_PORT` (по умолчанию `5433`), креды — из `infra/.env`.
- Хранение: named volume `postgres_data`; данные переживают перезапуск, удаляются только
  `docker compose down -v`.
- Проверено при настройке: контейнер `healthy`, данные сохраняются после `docker compose restart`.

**План** ([`AGENTS.md`](../AGENTS.md) §4–5):

- Реляционная схема: `users`, `resumes`, `vacancies`, `topics`, `topic_prerequisites`,
  `user_skill_states`, `interview_sessions` / `interview_turns`, `agent_actions`,
  `learning_plans` / `plan_items`, `embeddings` (pgvector).
- ORM: SQLAlchemy 2 (async); миграции: Alembic — появятся в `backend/`.
- Граф знаний на MVP — реляционная модель в Postgres, доступ через репозиторий-границу.

---

## 9. Внешние интеграции

**Реализованных нет.**

**План** ([`AGENTS.md`](../AGENTS.md) §6): LLM-провайдер — OpenAI (запасной вариант — Anthropic)
через провайдер-агностичный слой; function-calling + структурный JSON. Расположение в коде
появится в `backend/`.

---

## 10. Тесты

**Факт:** каталогов и файлов тестов нет; тестовый фреймворк не подключён.

**План** ([`AGENTS.md`](../AGENTS.md) §9): pytest + httpx; функциональные тесты, агентские
(на мок-LLM), сценарные e2e, тесты адаптивности, eval-наборы качества LLM.

---

## 11. Скрипты

Нет ни каталога `scripts/`, ни `Makefile`, ни npm-скриптов. Все существующие операции — команды
`docker compose` из [`infra/README.md`](../infra/README.md).

---

## 12. Генерируемые файлы

**Сейчас отсутствуют.**

- `infra/.env` — локальный файл (копия `.env.example`), в git не попадает.
- Уже перечислены в `.gitignore` (появятся с кодом): `.venv/`, `node_modules/`, `dist/`,
  `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage`, `*.log`.
- План: Alembic-миграции будут генерироваться (autogenerate) и коммититься; применённые ревизии
  вручную не редактируются.
