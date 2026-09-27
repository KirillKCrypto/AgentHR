"""Тесты базовых эндпоинтов приложения."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    """GET /health отвечает 200 и статусом ok."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body


def test_docs_is_available() -> None:
    """Swagger UI доступен."""
    response = client.get("/docs")

    assert response.status_code == 200
