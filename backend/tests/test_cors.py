"""Тесты CORS: frontend dev-сервер может обращаться к API."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ORIGIN = "http://localhost:5173"


def test_cors_allows_frontend_origin() -> None:
    """Ответ содержит CORS-заголовок для origin фронтенда."""
    response = client.get("/health", headers={"Origin": ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_cors_preflight_for_login() -> None:
    """Preflight-запрос POST /auth/login разрешён."""
    response = client.options(
        "/auth/login",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]
