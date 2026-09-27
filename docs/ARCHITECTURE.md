# ARCHITECTURE — AgentHR

> Навигация: [`INDEX.md`](../INDEX.md) → [`PROJECT_MAP.md`](PROJECT_MAP.md) → **ARCHITECTURE.md** (этот файл).
> Составлено по состоянию на 27.09.2026.
>
> Документ описывает систему на двух уровнях: **Факт** — что реально реализовано в репозитории;
> **План** — что зафиксировано в [`AGENTS.md`](../AGENTS.md), но кода ещё нет. Не смешивай уровни.

---

## 1. Обзор архитектуры

Стадия проекта — неделя 1 (M0 «Фундамент»). Фактически реализованы: инфраструктура (локальная
PostgreSQL 16 + pgvector в Docker Compose) и backend-каркас (FastAPI: health-эндпоинты,
JWT-аутентификация, настройки, async-подключение к БД, модель `User`, миграции Alembic,
тесты). Агентский цикл, остальные модели данных и внешние интеграции — пока нет.

Целевая архитектура — агентская система (не чат-бот): `LLM + Agent Harness + Tool Calling +
граф знаний + персистентная память + адаптивное обучение` ([`AGENTS.md`](../AGENTS.md) §1–2).

Далее каждый раздел разделён на «Факт» и «План».

---

## 2. Контекст системы

**Факт.** Система сейчас = контейнер базы данных и backend-сервер на машине разработчика.
Backend подключён к БД (asyncpg), регистрирует и аутентифицирует пользователей (JWT),
хранит таблицу `users`. Пользовательского взаимодействия извне пока нет.

**План.** Пользователь работает с системой через SPA по сценарию из 7 шагов: загрузка вакансии →
загрузка резюме → анализ уровня → персональный план подготовки → тренировочные интервью →
анализ ошибок → продолжение с накопленной памятью ([`README.md`](../README.md),
[`AGENTS.md`](../AGENTS.md) §1).

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
   └── uv run uvicorn app.main:app (backend/) ──▶ FastAPI (backend/app)
                                                     - GET /health, /health/db
                                                     - POST /auth/register, /auth/login, /auth/refresh
                                                     - GET /me (Bearer access)
                                                     - модель User (app/models/)
                                                     - Alembic-миграции (pgvector, users)
```

### 3.2 План (не реализовано)

Схема зафиксирована в [`AGENTS.md`](../AGENTS.md) §2.1:

```text
Frontend (React SPA)
    │ REST + WebSocket
Backend API (FastAPI)          ← auth, бизнес-логика, владелец БД, запуск сессий
    │
    ├── Agent Harness (LangGraph) ──► LLM Agent
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

**Ответственность:** предоставить локальную БД для разработки и backend.

**Основные компоненты:** `docker-compose.yml` (сервис `postgres`), `.env.example` / `.env`
(параметры подключения), `README.md` (инструкции).

**Зависимости:** Docker Desktop; внешних сервисов нет.

**Потребители:** разработчики; backend (подключение к `localhost:${POSTGRES_PORT}`).

**Ограничения:** данные в named volume; удаление — только `docker compose down -v`; порт на хосте
по умолчанию `5433` (5432 часто занят локальным PostgreSQL).

### Backend (каркас и auth реализованы)

**Location:** `backend/`

**Реализовано:** FastAPI-точка входа `app/main.py` (health-эндпоинты, подключение роутеров),
JWT-аутентификация (`app/api/`: `register`, `login`, `refresh`, `/me`; `app/core/security.py`:
argon2id + PyJWT), настройки `app/core/config.py` (pydantic-settings), слой БД `app/db/`
(async-движок, фабрика сессий, `get_db`, `Base`), модель `User` (`app/models/`), схемы
(`app/schemas/`), миграции Alembic (`alembic/`), тесты `tests/`.

**Ответственность по плану:** остальные модели и схема БД, доменные REST API, сервисный слой,
запуск агентских сессий, трансляция стрима; владелец БД ([`AGENTS.md`](../AGENTS.md) §2.2).

**Стек:** Python 3.13, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, PyJWT, pwdlib (argon2),
LangGraph.

### Frontend (План)

React + TypeScript + Vite, 7 экранов ([`AGENTS.md`](../AGENTS.md) §7). Без state-менеджеров —
данные через TanStack Query; UI — shadcn/ui.

### Agent Harness и Tools (План)

LangGraph-оркестратор: цикл агента, состояние, маршрутизация tool-calls, лимиты, audit-лог.
Tools — типизированные функции (JSON Schema), единственный способ агента дотянуться до данных
([`AGENTS.md`](../AGENTS.md) §2.2, §3.2–3.3).

### Граф знаний и векторный слой (План)

Онтология тем + зависимости + пользовательский срез (`topics`, `topic_prerequisites`,
`user_skill_states`); эмбеддинги — в pgvector ([`AGENTS.md`](../AGENTS.md) §4).

---

## 5. Потоки данных

**Факт:** доменные потоки отсутствуют (нет бизнес-логики). Есть поток аутентификации:
регистрация → argon2-хеш → `users`; логин → проверка хеша → пара JWT-токенов.

**План** ([`AGENTS.md`](../AGENTS.md) §2.4):

- **A. Onboarding:** вакансия + резюме → `extract_vacancy_requirements` / `extract_resume_skills`
  → нормализация к онтологии → обновление профиля знаний.
- **B. Планирование:** «требуется вакансией − текущий уровень» → gap-анализ → приоритизированный план.
- **C. Интервью (реалтайм):** генерация вопроса → ответ → `evaluate_answer` → обновление графа →
  `adjust_difficulty` → следующий вопрос → `save_interview_result` + отчёт.
- **D. Память:** старт с `load_user_profile`; накопленный профиль переиспользуется между вакансиями.

---

## 6. Поток запроса

**Факт** — маршруты в `backend/app/api/routes/` и `backend/app/main.py`:

- `GET /health` — статус и окружение (без обращения к БД);
- `GET /health/db` — `SELECT 1` через `get_db`: 200 / 503;
- `POST /auth/register` — валидация → argon2-хеш → `INSERT` (409 при занятом email);
- `POST /auth/login` — проверка пароля (401 при ошибке) → пара access/refresh-токенов;
- `POST /auth/refresh` — проверка refresh-токена → новая пара;
- `GET /me` — `get_current_user`: Bearer → проверка access-JWT → `SELECT` пользователя → 200/401.

**План:** REST + WebSocket между SPA и FastAPI; стриминг ответов агента пользователю
([`AGENTS.md`](../AGENTS.md) §2.1, §3.3).

---

## 7. Слой данных

**Факт:**

- СУБД: PostgreSQL 16 в контейнере `agenthr-postgres` (образ `pgvector/pgvector:pg16`).
- Расширение `vector` создаётся миграцией Alembic `6d7c8a1b787e`
  (`CREATE EXTENSION IF NOT EXISTS vector`; откат удаляет расширение).
- Таблица `users` создаётся миграцией `68cf3aa5da9d`: `id` (UUID, `gen_random_uuid()`),
  `email` (уникальный), `password_hash` (argon2id-хеш), `created_at` (`timestamptz`, `now()`).
  ORM-модель — `backend/app/models/user.py`.
- Подключение: `DATABASE_URL` из `backend/.env` (локальный дефолт в `app/core/config.py`);
  движок и сессии — `backend/app/db/session.py` (asyncpg, `pool_pre_ping`).
- Миграции: Alembic (async-шаблон), URL берётся в `alembic/env.py` из настроек;
  команды — `uv run alembic upgrade head` / `downgrade base` / `current`.
  Цикл upgrade → downgrade → upgrade проверен на локальной БД.

**План** ([`AGENTS.md`](../AGENTS.md) §4–5): остальные таблицы схемы (`vacancies`, `resumes`,
`topics`, `user_skill_states`, `interview_sessions`, `agent_actions` и др.); ORM-модели
SQLAlchemy 2 (async); `agent_actions` — обязательный audit-лог; граф знаний — реляционная
модель в Postgres с репозиторием-границей (без Neo4j в MVP).

---

## 8. Внешние интеграции

**Факт:** отсутствуют.

**План** ([`AGENTS.md`](../AGENTS.md) §6, §10):

| Параметр | Значение |
|---|---|
| Integration | LLM-провайдер (OpenAI; запасной — Anthropic), провайдер-агностичный слой |
| Purpose | анализ, планирование, генерация вопросов, оценка ответов |
| Location | появится в `backend/` (кода нет) |
| Configuration | API-ключ через переменные окружения (переменная появится вместе с кодом) |
| Data exchanged | тексты промптов/ответов, структурированный JSON (tool-calls, оценки) |
| Failure handling | план: лимиты итераций/бюджета, таймауты, fallback-ответ (§10) |

---

## 9. Конфигурация

**Факт** — `infra/.env` (копия `infra/.env.example`, в git не попадает):

| Переменная | Назначение | Секрет |
|---|---|---|
| `POSTGRES_USER` | логин суперпользователя контейнера | да |
| `POSTGRES_PASSWORD` | пароль | да |
| `POSTGRES_DB` | имя базы, создаваемой при инициализации | нет |
| `POSTGRES_PORT` | порт БД на хосте (по умолчанию `5433`) | нет |

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

Значения переменных окружения в документации не приводятся. `.env.example` — шаблоны для
локальной разработки, они коммитятся. Настройки читает `app/core/config.py` (pydantic-settings).

Прочие конфигурационные файлы: `.editorconfig`, `.gitattributes`, `.gitignore`,
`backend/alembic.ini`, `backend/.python-version` (пин Python 3.13).

**План:** конфигурация frontend появится вместе с кодом.

---

## 10. Аутентификация / авторизация

**Факт:** JWT (access + refresh), сервер не хранит сессии:

- `POST /auth/register` — argon2id-хеш пароля (`pwdlib`), 409 при занятом email;
- `POST /auth/login` — проверка пароля (одинаковый 401 для неверного пароля и неизвестного
  email; фиктивный хеш выравнивает время ответа), выдача пары токенов (`PyJWT`, HS256;
  claims `sub`/`type`/`iat`/`exp`);
- `POST /auth/refresh` — новая пара по refresh-токену;
- `GET /me` — защищённый эндпоинт (зависимость `get_current_user`, `HTTPBearer`).

Access-TTL — 30 минут, refresh-TTL — 30 дней (настройки). Секрет — `JWT_SECRET_KEY`
(dev-дефолт в коде, в продакшене обязательно переопределить). Refresh-токены stateless.

**План** ([`AGENTS.md`](../AGENTS.md) §6, §10): изоляция данных по `user_id` на уровне Tools;
при необходимости отзыва токенов — таблица refresh-сессий (отдельный шаг).

---

## 11. Фоновая обработка

**Факт:** отсутствует (нет воркеров, очередей, jobs).

**План:** в MVP отдельный компонент не выделен; в рисках упомянут «отдельный воркер агента» как
возможное решение для латентности стрима ([`AGENTS.md`](../AGENTS.md) §10).

---

## 12. Обработка ошибок

**Факт:** `/health/db` отвечает 503 при недоступной БД (`SQLAlchemyError`/`OSError`);
auth-эндпоинты — 401 (неверные данные/токен), 409 (дубликат email), 422 (валидация Pydantic).
Другой обработки ошибок нет.

**План** ([`AGENTS.md`](../AGENTS.md) §9–10): валидация схем `tool_call`, откат при ошибке
инструмента, лимиты/таймауты, fallback-ответ агента.

---

## 13. Тестирование

**Факт:** подключён pytest (+ `pytest-asyncio`); в `backend/tests/` 20 тестов:

- `test_health.py` — `/health` и `/docs`;
- `test_health_db.py` — `/health/db`: 200 и 503 (через подмену `get_db`, без реального Postgres);
- `test_user_model.py` — вставка/чтение `User` в реальной БД (пропускается, если БД недоступна);
- `test_auth.py` — register/login/me/refresh и негативные кейсы (дубликат email, неверный пароль,
  отсутствие/битый/просроченный токен, refresh вместо access) через `httpx2.AsyncClient`
  и `ASGITransport`.

Запуск: `uv run pytest` из `backend/`; конфигурация — в `backend/pyproject.toml`.

**План** ([`AGENTS.md`](../AGENTS.md) §9): функциональные тесты, агентские (на мок-LLM), сценарные
e2e, тесты адаптивности на синтетических пользователях, eval-наборы для качества LLM (извлечение,
оценка ответов).

---

## 14. Сборка и запуск

**Факт.** Инфраструктура (из [`infra/README.md`](../infra/README.md)):

```powershell
cd infra
Copy-Item .env.example .env   # один раз
docker compose up -d          # запуск БД
docker compose ps             # проверка статуса (healthy)
docker compose down           # остановка (данные сохраняются)
docker compose down -v        # остановка + удаление данных
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

Миграции применяются вручную (`alembic upgrade head`); автоматического применения при старте
приложения нет. Dockerfile приложений и CI нет. Платформа разработки — Windows + Docker Desktop + uv.

**План:** сборка frontend (Vite) — появится вместе с кодом.

---

## 15. Архитектурные ограничения

Зафиксированы в [`AGENTS.md`](../AGENTS.md) §2.3, §13 и обязательны к соблюдению:

1. LLM не обращается к БД/графу напрямую — только через Tools.
2. Все действия агента логируются (`agent_actions`, audit-лог).
3. Состояние сессии сохраняется (checkpoint) — сессию можно продолжить/восстановить.
4. Новое состояние — только через миграции Alembic.
5. Каждый инструмент — с JSON Schema, валидацией и записью в audit-лог.
6. Frontend: без state-менеджеров, анимаций и кастомных визуализаций без явного запроса.
7. Граф знаний на MVP — реляционная модель в Postgres; доступ через репозиторий-границу
   (для возможной миграции на Neo4j/AGE без переписывания агента).
8. Язык: документация и комментарии — русский; коммиты — английский (conventional commits);
   идентификаторы — латиница.

---

## 16. Известные архитектурные риски

- **Порт БД.** 5432 часто занят локальным PostgreSQL; проект использует 5433. При смене порта
  синхронизировать `infra/.env` и `DATABASE_URL` в `backend/.env`.
- **Зависимость от Docker Desktop.** При выключенном движке команды `docker compose` не работают,
  а `/health/db` отвечает 503.
- **Миграции вручную.** Автоприменения миграций при старте нет — перед запуском нужен
  `alembic upgrade head`.
- **Аутентификация MVP.** Refresh-токены stateless (отозвать до истечения нельзя); dev-дефолт
  `JWT_SECRET_KEY` нельзя использовать в продакшене.
- **Стадия проекта.** Значительная часть архитектуры существует только в плане; риск расхождения
  документации и кода снижается правилом обновлять эти три документа при изменениях.
- **Плановые риски проекта** (точность оценки ответов, качество онтологии, стоимость agent-loop,
  приватность и др.) перечислены в [`AGENTS.md`](../AGENTS.md) §10 — здесь не дублируются.
