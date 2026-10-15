# Infra

Инфраструктура локальной разработки: Docker Compose с двумя сервисами.

| Сервис | Контейнер | Что это | Порт на хосте |
|---|---|---|---|
| `postgres` | `agenthr-postgres` | PostgreSQL 16 + pgvector | `POSTGRES_PORT` (по умолчанию `5433`) |
| `api` | `agenthr-api` | backend-приложение (образ из `backend/Dockerfile`) | `API_PORT` (по умолчанию `8000`) |

## Запуск

```powershell
cd infra
Copy-Item .env.example .env   # один раз, локальные значения не коммитятся
docker compose up -d          # первый раз соберёт образ API
```

Проверка: `docker compose ps` — оба контейнера должны быть `healthy`.

API доступен на `http://127.0.0.1:8000` (+ `/docs`). Контейнер `api` при старте сам применяет
миграции Alembic, поэтому отдельно запускать `alembic upgrade head` для контейнерной БД не нужно.

## Изменения кода backend

Код копируется в образ (монтирования нет) — после правок нужна пересборка:

```powershell
docker compose up -d --build
docker compose logs -f api     # логи: миграции + uvicorn
```

## Подключение к БД

- Хост `localhost`, порт из `POSTGRES_PORT` в `.env` (по умолчанию `5433` — 5432 часто занят локальным PostgreSQL)
- Пользователь / пароль / база — из `.env` (по умолчанию `agenthr` / `agenthr` / `agenthr`)
- Внутри compose-сети контейнер `api` подключается к БД по `postgres:5432`

```powershell
docker compose exec postgres psql -U agenthr -d agenthr -c "SELECT version();"
docker compose exec postgres psql -U agenthr -d agenthr -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
docker compose exec postgres psql -U agenthr -d agenthr -c "\dt"
```

## Настройки API

Передаются в контейнер `api` из `infra/.env` (шаблон — `.env.example`): `API_PORT`,
`JWT_SECRET_KEY`, `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `CORS_ORIGINS`.
По умолчанию `LLM_PROVIDER=mock` — сеть не нужна.

## Остановка

```powershell
docker compose down      # остановить, данные сохраняются в volume
docker compose down -v   # остановить и удалить все данные
```

## Возможные проблемы

- `Bind for 0.0.0.0:5433 failed: port is already allocated` — порт `5433` или `8000` занят
  другим проектом (другой compose-стек, локальный PostgreSQL). Освободите порт или измените
  `POSTGRES_PORT` / `API_PORT` в `.env` и перезапустите.
- Контейнер `api` перезапускается по кругу — смотрите `docker compose logs api`: обычно это
  неудачная миграция или недоступная БД.
- Изменения кода не видны — образ не пересобран: `docker compose up -d --build`.
