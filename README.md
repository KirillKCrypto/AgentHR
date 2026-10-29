# AgentHR

Интеллектуальная агентская система адаптивной подготовки к техническим собеседованиям
под конкретную вакансию.

AgentHR изучает уровень пользователя, формирует профиль знаний, выявляет пробелы
и адаптирует подготовку под каждую новую вакансию. Это не чат-бот, а агентская система:

```text
LLM + Agent Harness + Tool Calling + Knowledge Graph + Persistent Memory + Adaptive Learning
```

## Возможности

- загрузка вакансии и резюме;
- извлечение навыков и нормализация к онтологии;
- профиль знаний и gap-анализ;
- provisional-темы для новых навыков, автоматическое и ручное ревью;
- группы требований `AND/OR` и критичность `must_have` / `nice_to_have`;
- две метрики: `coverage_all` и `confirmed_readiness`.

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
Следующий этап — evidence/verified level; следующая продуктовая веха — M3.

## Документация

- [`AGENTS.md`](AGENTS.md) — точка входа для агентов: стек, запуск, правила.
- [`INDEX.md`](INDEX.md) — карта документации.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — архитектура и потоки данных.
- [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) — карта модулей и файлов.
- [`docs/ONTOLOGY.md`](docs/ONTOLOGY.md) — онтология и оценка.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — план, экраны, тесты, риски.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — принятые решения.
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — термины.
- [`backend/README.md`](backend/README.md), [`frontend/README.md`](frontend/README.md),
  [`infra/README.md`](infra/README.md) — компонентные инструкции.
