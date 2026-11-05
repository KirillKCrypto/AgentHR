"""Планы подготовки: выбор тем из резюме и API."""

import pytest

from tests.conftest import ApiUser

RESUME_SKILLS = [
    {"name": "Python", "proficiency": 90, "evidence": "основной язык", "confidence": 0.9},
    {"name": "SQL", "proficiency": 80, "evidence": "запросы", "confidence": 0.8},
    {"name": "Docker", "proficiency": 70, "evidence": "контейнеры", "confidence": 0.7},
    {"name": "FastAPI", "proficiency": 60, "evidence": "сервисы", "confidence": 0.6},
    {"name": "Redis", "proficiency": 50, "evidence": "кэш", "confidence": 0.5},
    {"name": "Kafka", "proficiency": 40, "evidence": "очереди", "confidence": 0.4},
]


async def _create_resume(api_user: ApiUser) -> None:
    """Загружает резюме с шестью темами."""
    api_user.provider.responses["resume_skills"] = {
        "experience_years": 3.0,
        "self_level": "middle",
        "skills": RESUME_SKILLS,
    }
    response = await api_user.client.post(
        "/resumes",
        json={"title": "Резюме", "raw_text": "Опыт Python, SQL, Docker, FastAPI, Redis, Kafka"},
        headers=api_user.headers,
    )
    assert response.status_code == 201, response.text


async def test_create_plan_from_resume(api_user: ApiUser) -> None:
    """План берёт темы из профиля и сортирует по силе навыка."""
    await _create_resume(api_user)

    response = await api_user.client.post("/plans", json={}, headers=api_user.headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["vacancy_id"] is None
    assert 5 <= len(body["items"]) <= 12
    assert body["items"][0]["topic_key"] == "python"
    assert body["items"][0]["current_level"] == 90
    assert body["items"][0]["priority"] == pytest.approx(90 * (0.6 + 0.4 * 0.9), abs=0.01)
    assert all(item["target_level"] == 100 for item in body["items"])


async def test_create_plan_uses_vacancy_targets(api_user: ApiUser) -> None:
    """Если вакансия выбрана, цель по теме берётся из её требований."""
    await _create_resume(api_user)
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": "Redis",
                "required_level": 80,
                "weight": 1.0,
                "evidence": "кэш",
                "confidence": 0.9,
            }
        ],
    }
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "Нужен Redis"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text

    response = await api_user.client.post(
        "/plans",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    redis = next(item for item in body["items"] if item["topic_key"] == "redis")
    assert redis["target_level"] == 80
    assert "требуется 80" in redis["reason"]
    assert body["vacancy_title"] == "Backend"


async def test_plan_requires_profile(api_user: ApiUser) -> None:
    """Без резюме план не строится."""
    response = await api_user.client.post("/plans", json={}, headers=api_user.headers)

    assert response.status_code == 422
    assert "Профиль пуст" in response.json()["detail"]


async def test_plan_rejects_foreign_vacancy(api_user: ApiUser, second_user: ApiUser) -> None:
    """Чужую вакансию нельзя привязать к плану."""
    await _create_resume(api_user)
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Чужая",
        "company": "Other",
        "level": "middle",
        "skills": [],
    }
    vacancy = await second_user.client.post(
        "/vacancies",
        json={"title": "Чужая", "raw_text": "Текст"},
        headers=second_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text

    response = await api_user.client.post(
        "/plans",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )

    assert response.status_code == 404


async def test_get_and_list_plans(api_user: ApiUser) -> None:
    """Созданный план доступен по id и в списке."""
    await _create_resume(api_user)
    created = await api_user.client.post("/plans", json={}, headers=api_user.headers)
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]

    detail = await api_user.client.get(f"/plans/{plan_id}", headers=api_user.headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == plan_id

    listing = await api_user.client.get("/plans", headers=api_user.headers)
    assert listing.status_code == 200
    assert listing.json()[0]["topic_count"] == len(created.json()["items"])
