# Backend

Backend-приложение AgentHR на FastAPI. Реализованы: каркас, health-эндпоинты,
JWT-аутентификация, слой LLM (mock/OpenAI), подключение к БД, Agent Harness на Deep Agents,
модели User/AgentAction/граф знаний и онтология v1 с идемпотентным сидом.

Стек: Python 3.13, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, PyJWT, pwdlib (argon2),
openai, Deep Agents (LangGraph + LangChain core). Образ контейнера — `python:3.13-slim` + uv.

## Запуск

```powershell
uv sync
Copy-Item .env.example .env              # один раз, локальные настройки не коммитятся
uv run alembic upgrade head              # применить миграции (нужна запущенная БД из infra/)
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000, документация — /docs
```

## Запуск в контейнере

```powershell
cd ../infra
docker compose up -d --build    # agenthr-api на http://127.0.0.1:8000
```

- Образ — `backend/Dockerfile`: `python:3.13-slim` + uv, зависимости из `uv.lock`
  (`uv sync --frozen --no-dev`).
- `docker/entrypoint.sh` при старте применяет миграции (`alembic upgrade head`) и запускает
  uvicorn на `0.0.0.0:8000`.
- Настройки контейнера — в `infra/.env`; `DATABASE_URL` внутри compose-сети указывает на
  `postgres:5432` (задаётся в `infra/docker-compose.yml`).
- Тесты и ruff в образ не входят (dev-зависимости) — запускайте их локально через `uv run`.

## Эндпоинты

- `GET /health`, `GET /health/db` — проверки работоспособности;
- `POST /auth/register` — регистрация `{email, password}` → 201 (409, если email занят);
- `POST /auth/login` — вход `{email, password}` → `{access_token, refresh_token, token_type}`;
- `POST /auth/refresh` — обновление пары токенов `{refresh_token}`;
- `GET /me` — текущий пользователь (заголовок `Authorization: Bearer <access_token>`).

## LLM

- По умолчанию `LLM_PROVIDER=mock` — детерминированный провайдер для тестов, сеть не нужна.
- Для реальных вызовов: `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL` в `backend/.env`.
- Интерфейс (`app/llm/base.py`): `generate_with_tools` (function calling) и
  `generate_structured` (структурированный JSON по схеме).

## Agent Harness

- `app/agent/deep_harness.py` — основной harness: `deepagents.create_deep_agent` (цикл агента),
  лимиты (`AGENT_MAX_STEPS`, `AGENT_TOKEN_BUDGET`, `AGENT_TIMEOUT_SECONDS`), checkpointer по `thread_id`.
- `app/agent/middleware.py` — наши правила в цикле: аудит каждого вызова LLM и инструмента
  в таблицу `agent_actions`, остановка по лимитам, возврат ошибок инструментов модели.
- `app/agent/langchain_model.py` / `langchain_tools.py` — адаптеры: наш `LLMProvider` и реестр
  Tools (JSON Schema) для LangChain/Deep Agents.
- Агент получает дефолтный состав Deep Agents: инструменты файловой системы (управление
  контекстом) и сабагента `task`.

## Онтология и граф знаний

- `app/ontology/topics.py` — онтология v1: 8 тем с описаниями, алиасами и пререквизитами
  (`REQUIRES`); описания используются как текст для эмбеддингов при нормализации навыков.
- `app/ontology/graph.py` — операции над графом: поиск циклов, топологический порядок,
  транзитивные пререквизиты.
- `app/ontology/seed.py` — идемпотентный сид: темы обновляются по ключу, рёбра синхронизируются
  точно; автосозданные темы (из кандидатов) сид не трогает.

```powershell
uv run python -m app.ontology.seed    # засеять онтологию (нужна запущенная БД)
```

Онтология — словарь верхнего уровня, а не фильтр: навыки без темы сохраняются как есть
(`raw_name`) и попадают в `topic_candidates` — пул тем на ревью.

## Анализ и нормализация

- `app/services/analysis.py` — извлечение требований вакансии и навыков резюме
  (`extract_vacancy_requirements`, `extract_resume_skills`) через структурированный вывод LLM:
  JSON Schema, значения вне 0..100 обрезаются, пустые навыки отбрасываются.
- `app/services/normalization.py` — сопоставление навыка с темой онтологии:
  `exact` → `alias` → нечёткое совпадение → косинусная близость (`embedding`).
  Нормализация учитывает регистр, пунктуацию и кириллические омоглифы («ООП» = «OOP»).
- `app/services/topics.py` — индекс тем из БД (`load_topic_index`) и из пакета онтологии
  (`load_packaged_topic_index`, детерминированные id — для тестов и офлайна).
- `app/services/evaluation.py` — метрики качества извлечения (precision / recall / F1).

## Эмбеддинги

- `app/embeddings/` — слой эмбеддингов: `none` (по умолчанию), `local` (ONNX-модель
  в процессе, без внешних сервисов) и `mock` (тесты).
- Локальная модель: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 измерения,
  понимает русский). Ставится отдельной экстра-группой и не тянется в базовый образ:

```powershell
uv sync --extra embeddings
uv run python -c "from app.embeddings import create_embedding_provider; from app.core.config import Settings; print(create_embedding_provider(Settings(embedding_provider='local')).available)"
```

- Без эмбеддера нормализация продолжает работать по алиасам и нечёткому совпадению —
  провайдер просто сообщает `available = False`.

## Качество извлечения

Golden-набор лежит в `tests/fixtures/extraction_golden.py`: тексты документов, записанные ответы
модели, эталонные навыки и ожидаемые темы. Тесты проверяют весь конвейер детерминированно,
а скрипт меряет качество на живой модели:

```powershell
uv run python scripts/eval_extraction.py --min-f1 0.8 --show-skills
```

Для живого прогона нужен `LLM_PROVIDER=openai` с ключом и моделью.

## Тесты и линтер

```powershell
uv run pytest
uv run ruff check .
```

## Миграции

```powershell
uv run alembic upgrade head                        # применить все миграции
uv run alembic current                             # текущая ревизия
uv run alembic downgrade base                      # откатить всё
uv run alembic revision --autogenerate -m "..."    # новая миграция по моделям
```

URL БД берётся из настроек (`backend/.env`, переменная `DATABASE_URL`); в коде есть локальный
дефолт. Применённые миграции вручную не редактируются.

## Структура

- `app/main.py` — точка входа FastAPI: роутеры, `/health`, `/health/db`
- `app/api/` — роутеры (`routes/auth.py`, `routes/users.py`) и зависимости (`deps.py`)
- `app/core/config.py` — настройки (pydantic-settings, читает `.env`)
- `app/core/security.py` — argon2-хеши паролей, выпуск/проверка JWT
- `app/agent/` — harness на Deep Agents, реестр Tools (JSON Schema), middleware аудита/лимитов
- `Dockerfile` — образ backend (uv, без dev-зависимостей)
- `docker/entrypoint.sh` — старт контейнера: `alembic upgrade head` → uvicorn
- `app/db/session.py` — async-движок, фабрика сессий, зависимость `get_db`
- `app/db/base.py` — базовый класс моделей (`Base`)
- `app/llm/` — слой LLM: `base.py` (интерфейс), `mock.py`, `openai.py`, `factory.py`
- `app/models/` — ORM-модели (`User`, `AgentAction`, `Topic`, `TopicPrerequisite`, `TopicCandidate`,
  `Vacancy`, `VacancySkill`, `Resume`, `ResumeSkill`, `UserSkillState`)
- `app/ontology/` — онтология v1, операции над графом зависимостей, идемпотентный сид
- `app/embeddings/` — слой эмбеддингов (none / local ONNX / mock)
- `app/services/` — сервисный слой: анализ (извлечение), нормализация, метрики качества
- `app/schemas/` — Pydantic-схемы (сейчас `auth.py`)
- `alembic/` — миграции (async), `alembic/versions/`
- `scripts/eval_extraction.py` — eval качества извлечения на живой модели
- `tests/` — тесты (pytest + httpx2, интеграционные требуют запущенную БД)

## Безопасность (важно)

`JWT_SECRET_KEY` в коде — только dev-дефолт; в продакшене обязательно задавать через окружение.
Refresh-токены stateless: отзыв до истечения не поддерживается (осознанный компромисс MVP).
Ключ `OPENAI_API_KEY` — только через окружение.

Дальше по плану (см. `AGENTS.md`): M2 — извлечение требований вакансии и навыков резюме,
нормализация к онтологии, профиль знаний и доменные REST API.
