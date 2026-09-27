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
- **Текущее состояние:** реализована **только инфраструктура** — Docker Compose с PostgreSQL 16 +
  pgvector (`infra/`). Кода приложения нет: `backend/` и `frontend/` содержат только README-заглушки.
  Из чеклиста старта ([`AGENTS.md`](AGENTS.md), §12) выполнены пункты 1–2; пункты 3–11 не начаты.

---

## 2. Быстрый старт

Сейчас запускается только база данных. Требование: Docker Desktop с запущенным движком.

```powershell
cd infra
Copy-Item .env.example .env   # один раз: локальные креды, в git не попадают
docker compose up -d
docker compose ps             # agenthr-postgres должен перейти в healthy
```

Проверка БД и расширения `vector`, остановка — команды в [`infra/README.md`](infra/README.md).
Команды запуска backend/frontend появятся вместе с кодом.

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
├── backend/             — ПЛАН: FastAPI, Agent Harness, tools; сейчас только README.md
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

### Backend — план (кода нет)

**Path:** `backend/` — пока только `README.md`.

По плану здесь разместятся: REST API (FastAPI), Agent Harness (LangGraph), реестр Tools,
слой БД (SQLAlchemy + Alembic), JWT-auth, провайдер-агностичный слой LLM.

Источник: [`AGENTS.md`](AGENTS.md) §2–3, §6.

### Frontend — план (кода нет)

**Path:** `frontend/` — пока только `README.md`.

По плану: React SPA, 7 экранов (`/login`, дашборд, загрузка вакансии, профиль, план, интервью,
отчёт). Источник: [`AGENTS.md`](AGENTS.md) §7.

### Документация и управление

**Path:** `README.md`, `AGENTS.md`, `INDEX.md`, `docs/`

Описание проекта, требования/правила и навигация по репозиторию.

---

## 5. Обзор архитектуры

**Фактически сейчас** (единственный работающий контур):

```text
Машина разработчика
      │  docker compose up -d   (infra/)
      ▼
Контейнер agenthr-postgres: PostgreSQL 16 + pgvector
      │
      ▼
Named volume postgres_data — данные переживают перезапуск
```

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
| Точка входа backend (FastAPI) | основной сервер приложения | не создана |
| Точка входа frontend (Vite) | SPA | не создана |
| Тесты (pytest) | прогон тестов | тестов нет |

Других исполняемых точек входа в репозитории нет.

---

## 7. Важные файлы

| Файл | Роль |
|---|---|
| `AGENTS.md` | требования, план на 8 недель, архитектурные правила, глоссарий — главный источник истины по замыслу |
| `README.md` | краткое описание проекта и стека |
| `infra/docker-compose.yml` | описание контейнера с БД |
| `infra/.env.example` | шаблон локального окружения (креды, порт) |
| `infra/README.md` | команды запуска/проверки/остановки БД |
| `.gitignore` | исключения git (`.env`, `.venv`, `node_modules` и др.) |
| `backend/README.md`, `frontend/README.md` | заглушки будущих подсистем |

---

## 8. Карта документации

```text
INDEX.md                    — главная точка входа (этот файл)
├── docs/PROJECT_MAP.md     — где находятся каталоги и файлы, за что отвечают
├── docs/ARCHITECTURE.md    — как компоненты связаны между собой, потоки данных
├── AGENTS.md               — исходные требования, план, архитектурные правила
├── README.md               — краткое описание проекта
└── infra/README.md         — работа с локальной БД
```

---

## 9. Критические области

- **`AGENTS.md`** — источник правил и плана. При изменениях проверять согласованность
  `INDEX.md` / `docs/PROJECT_MAP.md` / `docs/ARCHITECTURE.md` и что план не выдан за факт.
- **`infra/docker-compose.yml`** — от него зависит БД всей команды. Изменение порта, volume или
  healthcheck затрагивает: `infra/.env`, `infra/README.md`, будущие настройки backend.
- **`infra/.env`** — локальный файл с кредами; в git не коммитится, значения не документируются.
- **Порт БД** — на хосте по умолчанию `5433` (5432 часто занят локальным PostgreSQL); при смене
  синхронизировать `.env` и будущую конфигурацию backend.

---

## 10. Generated / Do Not Edit

Автогенерируемых файлов в репозитории **сейчас нет** (нет кода, миграций и сборок). Правила:

- `infra/.env` — локальный файл, не коммитить; значения не включать в документацию.
- Появятся позже: `.venv/`, `node_modules/`, `dist/`, `__pycache__/`, кэши тестов — уже
  перечислены в `.gitignore`.
- Когда появятся Alembic-миграции: уже применённые ревизии вручную не редактировать.

---

## 11. AI Agent Rules

1. Перед изменением кода определи подсистему и её ответственность по этому файлу и
   [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md).
2. Не придумывай несуществующие модули: `backend/` и `frontend/` пока пусты. Перед созданием
   файла проверь, что его ещё нет.
3. Соблюдай архитектурные правила проекта ([`AGENTS.md`](AGENTS.md) §2.3, §13): LLM не обращается
   к БД/графу напрямую — только через Tools; все действия агента логируются; состояние сессии
   сохраняется (checkpoint).
4. Новое состояние БД — только через миграции Alembic (когда появится backend).
5. Не трогай секреты: `infra/.env` не коммитить, значения не документировать.
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
| Где API и бизнес-логика? | Пока нет; план — `backend/` ([`AGENTS.md`](AGENTS.md) §2–3) |
| Где агент, Harness и Tools? | Пока нет; план — `backend/` ([`AGENTS.md`](AGENTS.md) §3) |
| Где фронтенд? | Пока нет; план — `frontend/` ([`AGENTS.md`](AGENTS.md) §7) |
| Где работа с БД (модели, миграции)? | Пока нет; реализована только сама БД — `infra/` |
| Где конфигурация окружения? | `infra/.env.example` (+ локальный `infra/.env`) |
| Где тесты? | Пока нет; план — pytest ([`AGENTS.md`](AGENTS.md) §9) |
| Где правила разработки? | [`AGENTS.md`](AGENTS.md) §13 |
| Где план на 8 недель? | [`AGENTS.md`](AGENTS.md) §8 |
| Где подробная карта файлов? | [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) |
| Где описание архитектуры? | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
