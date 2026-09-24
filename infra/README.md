# Infra

Инфраструктура локальной разработки: Docker Compose — PostgreSQL 16 + pgvector.

## Запуск

```powershell
cd infra
Copy-Item .env.example .env   # один раз, локальные креды не коммитятся
docker compose up -d
```

Проверка: `docker compose ps` — контейнер `agenthr-postgres` должен быть `healthy`.

## Подключение

- Хост `localhost`, порт из `POSTGRES_PORT` в `.env` (по умолчанию `5433` — 5432 часто занят локальным PostgreSQL)
- Пользователь / пароль / база — из `.env` (по умолчанию `agenthr` / `agenthr` / `agenthr`)

```powershell
docker compose exec postgres psql -U agenthr -d agenthr -c "SELECT version();"
docker compose exec postgres psql -U agenthr -d agenthr -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

## Остановка

```powershell
docker compose down      # остановить, данные сохраняются в volume
docker compose down -v   # остановить и удалить все данные
```
