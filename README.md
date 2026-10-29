# AgentHR

Интеллектуальная агентская система адаптивной подготовки к техническим собеседованиям
под конкретные вакансии.

Персональный AI-агент изучает уровень пользователя, формирует профиль знаний, выявляет
пробелы и адаптирует подготовку под каждую новую вакансию — с накоплением опыта между
тренировками.

## Ключевая идея

Это не чат-бот с LLM, а агентская система:

```
LLM + Agent Harness + Tool Calling + Knowledge Graph + Persistent Memory + Adaptive Learning
```

## Основной сценарий

1. Загрузка описания вакансии.
2. Загрузка резюме.
3. Анализ текущего уровня знаний.
4. Персональный план подготовки.
5. Тренировочные технические собеседования.
6. Анализ ошибок и рекомендации.
7. Продолжение подготовки на основе накопленного опыта.

## Технологии

| Слой | Стек |
|---|---|
| Backend | Python 3.13, FastAPI |
| Agent Harness | Deep Agents (LangGraph, LangChain core) |
| LLM | DeepSeek (OpenAI-совместимый слой, провайдер-агностичный) |
| Database | PostgreSQL 16 + pgvector |
| Knowledge Graph | Реляционная модель в Postgres |
| Frontend | React, TypeScript, Vite, TanStack Query, shadcn/ui |
| Real-time | WebSocket |
| Инфраструктура | Docker Compose, Alembic, pytest |

## Структура репозитория

- `backend/` — FastAPI-приложение, Agent Harness и инструменты
- `frontend/` — React SPA
- `infra/` — Docker Compose: PostgreSQL 16 + pgvector и backend API

## Документация

- **[AGENTS.md](./AGENTS.md)** — полный контекст проекта: архитектура, модель данных,
  AI-агент и инструменты, граф знаний, дорожная карта на 8 недель, риски и правила разработки.

## Статус

Проект в разработке. M0 «Фундамент» (неделя 1) и M1 «Agent Harness» (неделя 2) закрыты:
инфраструктура (PostgreSQL + pgvector и backend API в Docker Compose), база данных,
аутентификация, слой LLM, Agent Harness на Deep Agents (лимиты и аудит в `agent_actions`),
frontend со входом через UI. Для живого ответа LLM нужен ключ DeepSeek (см. `backend/README.md`).
M2 «Понимание кандидата» закрыт: схема графа знаний и документов, онтология v2
(89 атомарных навыков, 75 пререквизитов) и идемпотентный сид, извлечение навыков и нормализация, профиль
знаний и gap-анализ, доменные REST API (`/vacancies`, `/resumes`, `/profile`, `/analysis`),
экраны `/vacancies/new` и `/profile`, E2E-скелет сквозного сценария.
Дальше — M3: план подготовки и сессия интервью.
