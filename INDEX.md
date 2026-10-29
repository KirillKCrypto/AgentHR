# INDEX — документация AgentHR

Короткая карта документации. Для агентов точка входа — [`AGENTS.md`](AGENTS.md),
для людей — [`README.md`](README.md).

## Порядок чтения

1. [`AGENTS.md`](AGENTS.md) — краткий контекст, стек, запуск, правила.
2. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — как устроена система.
3. [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) — где находится код.
4. [`docs/ONTOLOGY.md`](docs/ONTOLOGY.md) — онтология и оценка навыков.
5. [`docs/ROADMAP.md`](docs/ROADMAP.md) — план, экраны, тесты, риски.
6. [`docs/DECISIONS.md`](docs/DECISIONS.md) — принятые решения.
7. [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — термины.

## Компонентные README

| Файл | О чём |
|---|---|
| [`backend/README.md`](backend/README.md) | backend: запуск, API, LLM, tools, тесты |
| [`frontend/README.md`](frontend/README.md) | frontend: экраны, API-клиент, сборка |
| [`infra/README.md`](infra/README.md) | Docker Compose, БД, диагностика |

## Быстрые ссылки

- API: `http://127.0.0.1:8000`, Swagger: `http://127.0.0.1:8000/docs`
- UI: `http://127.0.0.1:5173`
- Postgres: `localhost:5433`
- Тесты: `cd backend && uv run pytest -q`
- Frontend build: `cd frontend && npm.cmd run build`
