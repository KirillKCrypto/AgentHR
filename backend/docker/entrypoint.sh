#!/bin/sh
# Entrypoint backend-контейнера: применяет миграции и запускает uvicorn (без dev-reload).
set -e

echo "[entrypoint] Применяю миграции Alembic (alembic upgrade head)..."
alembic upgrade head

# Идемпотентный сид: без него в свежей БД нет canonical-тем, и авто-ревью
# не с чем сравнивать новые навыки.
echo "[entrypoint] Синхронизирую онтологию (python -m app.ontology.seed)..."
python -m app.ontology.seed

echo "[entrypoint] Запускаю uvicorn на 0.0.0.0:8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${UVICORN_WORKERS:-1}"
