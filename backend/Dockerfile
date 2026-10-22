# syntax=docker/dockerfile:1

# Образ backend-приложения AgentHR: FastAPI + Agent Harness.
# Сборка на uv, версии зависимостей — из uv.lock; dev-зависимости не ставятся.
FROM python:3.13-slim

# uv из официального образа; версия зафиксирована и совпадает с локальной разработкой
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Опциональные экстра-группы: embeddings — локальный ONNX-эмбеддер.
# Сборка с эмбеддингами: docker build --build-arg UV_EXTRAS="--extra embeddings" .
ARG UV_EXTRAS=""

# Слой зависимостей: манифесты копируются отдельно, чтобы кэш не сбрасывался при правках кода
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project $UV_EXTRAS

# Код приложения (миграции Alembic тоже нужны в образе — применяются на старте)
COPY . .
RUN uv sync --frozen --no-dev $UV_EXTRAS && chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
