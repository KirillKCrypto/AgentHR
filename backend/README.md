# Backend

Backend-приложение AgentHR на FastAPI. Реализованы: каркас, health-эндпоинты,
JWT-аутентификация, слой LLM (mock/OpenAI), подключение к БД, Agent Harness на Deep Agents,
модели User/AgentAction/граф знаний и онтология v2 с идемпотентным сидом, доменные REST API
(вакансии, резюме, профиль знаний, gap-анализ) и агентские tools поверх сервисного слоя.

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
- `GET /me` — текущий пользователь (заголовок `Authorization: Bearer <access_token>`);
- `POST /vacancies` — загрузка текста вакансии `{title?, company?, raw_text}`: извлечение
  требований LLM, нормализация к онтологии, запись навыков; 201 (422 — пустой/нечитаемый
  документ, 502 — LLM недоступна);
- `GET /vacancies`, `GET /vacancies/{id}` — список и карточка вакансии с навыками;
- `POST /resumes` — загрузка текста резюме: извлечение навыков, запись и пересборка профиля;
- `GET /resumes`, `GET /resumes/{id}` — список и карточка резюме;
- `GET /profile` — профиль знаний: уровень по темам онтологии + навыки вне онтологии;
- `GET /profile/gaps?vacancy_id=...` — разрывы между вакансией и профилем;
- `POST /analysis` — совместный анализ загруженных документов `{vacancy_id, resume_id}`:
  документы, профиль и разрывы одним ответом (без вызовов LLM — только чтение и расчёт).

Доменные эндпоинты требуют access-токен и изолированы по владельцу: чужой документ
возвращает 404, а не 403 — существование чужих записей не раскрывается.

## LLM

- По умолчанию `LLM_PROVIDER=mock` — детерминированный провайдер для тестов, сеть не нужна.
- Для реальных вызовов: `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL` в `backend/.env`.
  Для OpenAI-совместимых шлюзов задаётся `OPENAI_BASE_URL` (пусто — официальный `api.openai.com`).
- Интерфейс (`app/llm/base.py`): `generate_with_tools` (function calling) и
  `generate_structured` (структурированный JSON по схеме).
- Структурированный вывод: сначала штатный `response_format=json_schema`; если шлюз его
  не поддерживает или запрос не прошёл, провайдер один раз повторяет запрос с описанием
  схемы в промпте. Ответ очищается от markdown-обёртки и разбирается как JSON-объект.
- Таймауты и повторы: `OPENAI_TIMEOUT_SECONDS` (по умолчанию 30) и `OPENAI_MAX_RETRIES`
  (по умолчанию 0 — резервный запрос делает сам провайдер). Ошибки SDK и сети превращаются
  в `LLMError`; HTTP-контур отвечает 502 с понятным текстом, причина пишется в лог.

## Agent Harness

- `app/agent/deep_harness.py` — основной harness: `deepagents.create_deep_agent` (цикл агента),
  лимиты (`AGENT_MAX_STEPS`, `AGENT_TOKEN_BUDGET`, `AGENT_TIMEOUT_SECONDS`), checkpointer по `thread_id`.
- `app/agent/middleware.py` — наши правила в цикле: аудит каждого вызова LLM и инструмента
  в таблицу `agent_actions`, остановка по лимитам, возврат ошибок инструментов модели.
- `app/agent/langchain_model.py` / `langchain_tools.py` — адаптеры: наш `LLMProvider` и реестр
  Tools (JSON Schema) для LangChain/Deep Agents.
- Агент получает дефолтный состав Deep Agents: инструменты файловой системы (управление
  контекстом) и сабагента `task`.
- `app/agent/analysis_tools.py` — доменные инструменты: `extract_vacancy_requirements`,
  `extract_resume_skills`, `get_vacancy_requirements`, `get_user_skill_state`,
  `query_skill_dependencies`, `update_skill_proficiency`, `compute_vacancy_gaps`.
  Инструменты собираются под конкретного пользователя и сессию БД: `user_id` не приходит
  от модели, поэтому агент не может прочитать или изменить чужие данные.

## Онтология и граф знаний

- `app/ontology/topics.py` — онтология v2: 89 атомарных тем с описаниями, алиасами и пререквизитами
  (`REQUIRES`); описания используются как текст для эмбеддингов при нормализации навыков.
- `app/ontology/graph.py` — операции над графом: поиск циклов, топологический порядок,
  транзитивные пререквизиты.
- `app/ontology/seed.py` — идемпотентный сид: темы, рёбра и алиасы синхронизируются
  точно; provisional-темы и auto-алиасы сид не удаляет.

```powershell
uv run python -m app.ontology.seed    # засеять онтологию (нужна запущенная БД)
```

Онтология — словарь верхнего уровня, а не фильтр: для навыка без темы создаётся
provisional-тема, запись в `topic_aliases` и кандидат в `topic_candidates` на ревью.
Новые названия не остаются с `topic_id = NULL`; миграция `c9a1d2e3f4b5` заполняет
исторические NULL и делает `topic_id` обязательным. Лимит `AUTO_TOPIC_LIMIT`
(по умолчанию 10) отправляет overflow в одну review-тему.

## Анализ и нормализация

- `app/services/analysis.py` — извлечение требований вакансии и навыков резюме
  (`extract_vacancy_requirements`, `extract_resume_skills`) через структурированный вывод LLM:
  JSON Schema, значения вне 0..100 обрезаются, пустые навыки отбрасываются.
- `app/services/normalization.py` — сопоставление навыка с темой онтологии:
  `exact` → `alias` → нечёткое совпадение → косинусная близость (`embedding`).
  Нормализация учитывает регистр, пунктуацию и кириллические омоглифы («ООП» = «OOP»).
- `app/services/topics.py` — индекс canonical/provisional-тем и алиасов из БД
  (`load_topic_index`), индекс пакета (`load_packaged_topic_index`) и
  `resolve_or_create_topics()` — гарантия `topic_id` для каждого навыка.
- `app/services/evaluation.py` — метрики качества извлечения (precision / recall / F1).
- `app/services/profile.py` — запись документов и профиль знаний: `analyze_vacancy` /
  `save_vacancy_analysis`, `analyze_resume` / `save_resume_analysis`, `rebuild_profile`,
  `get_profile`, `compute_gaps`, `update_skill_proficiency`, `weighted_estimate`.
  Навыки без темы не теряются: для них создаётся provisional-тема и кандидат на ревью,
  поэтому новые строки всегда имеют `topic_id`.

### Профиль знаний и gap-анализ

- Оценка уровня по теме объединяется взвешенно по источнику: `manual 1.0`, `interview 0.9`,
  `assessment 0.8`, `resume 0.6`. Уверенность растёт по формуле независимых свидетельств
  `1 − Π(1 − c_i)` и ограничена `0.95`.
- Пересборка профиля по резюме не занижает более сильные источники (`interview`, `manual`,
  `assessment`): резюме обновляет только срез, построенный по резюме.
- Готовность к вакансии считается только по навыкам, сопоставленным с онтологией;
  навыки вне словаря показываются в разрывах и учитываются в `unmatched_count`.
- `POST /analysis` не вызывает LLM: извлечение выполняется при загрузке документов.

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

Сквозной сценарий M2 на уровне API — `tests/test_e2e_scenario.py`: вакансия → резюме →
профиль знаний → разрывы → `/analysis` → новая вакансия с переиспользованием профиля
(LLM подменена детерминированной заглушкой).

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

- `app/main.py` — точка входа FastAPI: роутеры, `/health`, `/health/db`, обработчик `LLMError`
- `app/api/` — роутеры (`routes/auth.py`, `routes/users.py`, `routes/vacancies.py`,
  `routes/resumes.py`, `routes/profile.py`, `routes/analysis.py`), зависимости (`deps.py`),
  маппинг доменных объектов в схемы (`mappers.py`)
- `app/core/config.py` — настройки (pydantic-settings, читает `.env`)
- `app/core/security.py` — argon2-хеши паролей, выпуск/проверка JWT
- `app/agent/` — harness на Deep Agents, реестр Tools (JSON Schema), middleware аудита/лимитов,
  доменные инструменты (`analysis_tools.py`)
- `Dockerfile` — образ backend (uv, без dev-зависимостей)
- `docker/entrypoint.sh` — старт контейнера: `alembic upgrade head` → uvicorn
- `app/db/session.py` — async-движок, фабрика сессий, зависимость `get_db`
- `app/db/base.py` — базовый класс моделей (`Base`)
- `app/llm/` — слой LLM: `base.py` (интерфейс), `mock.py`, `openai.py`, `factory.py`
- `app/models/` — ORM-модели (`User`, `AgentAction`, `Topic`, `TopicAlias`, `TopicPrerequisite`,
  `TopicCandidate`, `Vacancy`, `VacancySkill`, `Resume`, `ResumeSkill`, `UserSkillState`)
- `app/ontology/` — онтология v2, операции над графом зависимостей, идемпотентный сид
- `app/embeddings/` — слой эмбеддингов (none / local ONNX / mock)
- `app/services/` — сервисный слой: анализ (извлечение), нормализация, профиль и gap-анализ,
  метрики качества
- `app/schemas/` — Pydantic-схемы (`auth.py`, `analysis.py`)
- `alembic/` — миграции (async), `alembic/versions/`
- `scripts/eval_extraction.py` — eval качества извлечения на живой модели
- `tests/` — тесты (pytest + httpx2, интеграционные требуют запущенную БД); общие фикстуры —
  `tests/conftest.py` (пользователь API, второй пользователь, заглушка LLM по имени схемы)

## Безопасность (важно)

`JWT_SECRET_KEY` в коде — только dev-дефолт; в продакшене обязательно задавать через окружение.
Refresh-токены stateless: отзыв до истечения не поддерживается (осознанный компромисс MVP).
Ключ `OPENAI_API_KEY` — только через окружение.

Дальше по плану (см. `AGENTS.md`): M3–M4 — планировщик подготовки, сессии интервью
(`next_question`, `evaluate_answer`, `adjust_difficulty`), WebSocket-стриминг и отчёты.
