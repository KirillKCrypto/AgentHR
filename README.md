# AgentHR

Интеллектуальная агентская система адаптивной подготовки к техническим собеседованиям
под конкретную вакансию.

AgentHR изучает уровень пользователя, формирует профиль знаний, выявляет пробелы
и адаптирует подготовку под каждую новую вакансию. Это не чат-бот, а агентская система:

```text
LLM + Agent Harness + Tool Calling + Knowledge Graph + Persistent Memory + Adaptive Learning
```

## Возможности

- загрузка резюме текстом или файлом PDF/DOCX, профиль знаний с коэффициентом 0–100;
- загрузка вакансии отдельно: извлечение требований и сравнение с готовым профилем;
- извлечение навыков и нормализация к онтологии: версии, составные названия, синонимы;
- мини-тесты по ключевым навыкам: `claimed_level` vs `verified_level`;
- gap-анализ: требуется / в профиле / разрыв / достаточно;
- рекомендации «что подтянуть» и разрыв по обязательным требованиям;
- персональный план подготовки из 5–12 тем резюме;
- банк вопросов по темам и сложности, полная генерация через CLI;
- provisional-темы для новых навыков, автоматическое ревью;
- группы требований `AND/OR` и критичность `must_have` / `nice_to_have`;
- метрики: `coverage_all`, `confirmed_readiness`, `critical_readiness`, `average_gap`.

## Пользовательский сценарий

1. Пользователь загружает резюме на `/profile` — AgentHR извлекает навыки и строит профиль.
2. Каждая тема получает коэффициент `proficiency` 0–100 и уверенность `confidence` 0–1.
3. Пользователь загружает вакансию на `/vacancies/new` — требования сопоставляются с профилем.
4. Результат: готовность 0–100%, таблица разрывов и список тем «что подтянуть».
5. Из вакансии или профиля строится план подготовки, вопросы берутся из банка по темам.

## Стек

| Слой | Технология |
|---|---|
| Backend | Python 3.13, FastAPI |
| Agent Harness | Deep Agents (LangGraph + LangChain core) |
| LLM | DeepSeek (`deepseek-flash`), OpenAI-совместимый слой |
| Database | PostgreSQL 16 + pgvector |
| Frontend | React 19, TypeScript, Vite, TanStack Query, shadcn/ui |
| Инфраструктура | Docker Compose, Alembic, pytest |

## Быстрый старт

```powershell
# 1. База и API
cd infra
Copy-Item .env.example .env
docker compose up -d

# 2. UI
cd ../frontend
npm.cmd install
npm.cmd run dev
```

- API: `http://127.0.0.1:8000` (Swagger: `/docs`)
- UI: `http://127.0.0.1:5173`
- PostgreSQL: `localhost:5433`

Подробный запуск, локальный backend и тесты — в [`AGENTS.md`](AGENTS.md).

## Статус

M0–M2 закрыты. Онтология: этапы 1–4 закрыты (provisional-темы, backfill,
автоматическое и ручное ревью, две метрики покрытия, `AND/OR`, criticality).
Добавлены мини-тесты: 8 тем × 20 вопросов, тест из 10 вопросов,
`claimed_level` и `verified_level`, один тест на тему.
Следующий этап — расширение банка и адаптивные тесты; следующая веха — M3.

## Документация

- [`AGENTS.md`](AGENTS.md) — точка входа для агентов: стек, запуск, правила.
- [`INDEX.md`](INDEX.md) — карта документации.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — архитектура и потоки данных.
- [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) — карта модулей и файлов.
- [`docs/ONTOLOGY.md`](docs/ONTOLOGY.md) — онтология и оценка.
- [`docs/ASSESSMENT.md`](docs/ASSESSMENT.md) — мини-тесты и verified level.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — план, экраны, тесты, риски.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — принятые решения.
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — термины.
- [`backend/README.md`](backend/README.md), [`frontend/README.md`](frontend/README.md),
  [`infra/README.md`](infra/README.md) — компонентные инструкции.
