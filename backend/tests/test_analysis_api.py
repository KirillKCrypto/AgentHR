"""Интеграционные тесты API анализа: вакансии, резюме, профиль и разрывы."""

import pytest

from tests.conftest import RESUME_TEXT, VACANCY_TEXT, ApiUser


async def _create_vacancy(user: ApiUser) -> dict:
    """Создаёт вакансию через API."""
    response = await user.client.post(
        "/vacancies",
        json={"title": "Python-разработчик", "company": "Acme", "raw_text": VACANCY_TEXT},
        headers=user.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_resume(user: ApiUser) -> dict:
    """Создаёт резюме через API."""
    response = await user.client.post(
        "/resumes",
        json={"title": "Резюме", "raw_text": RESUME_TEXT},
        headers=user.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_vacancy_extracts_and_matches_skills(api_user: ApiUser) -> None:
    """Вакансия сохраняется с извлечёнными навыками и темами онтологии."""
    body = await _create_vacancy(api_user)

    assert body["title"] == "Python-разработчик"
    assert body["company"] == "Acme"
    assert body["user_id"] == api_user.user_id

    skills = {skill["raw_name"]: skill for skill in body["skills"]}
    assert set(skills) == {"Python", "PostgreSQL", "Kafka"}
    assert skills["Python"]["topic"]["key"] == "python"
    assert skills["Python"]["match_method"] == "exact"
    assert skills["Python"]["level"] == 70
    assert skills["PostgreSQL"]["topic"]["key"] == "postgresql"
    assert skills["PostgreSQL"]["match_method"] == "exact"
    # В онтологии v2 Kafka — отдельный навык, а не «вне словаря»
    assert skills["Kafka"]["topic"]["key"] == "kafka"
    assert skills["Kafka"]["match_method"] == "exact"


async def test_resume_updates_profile(api_user: ApiUser) -> None:
    """Резюме создаёт срез профиля знаний и сохраняет навыки вне онтологии."""
    resume = await _create_resume(api_user)
    assert {skill["raw_name"] for skill in resume["skills"]} == {"Python", "SQL", "Docker"}

    response = await api_user.client.get("/profile", headers=api_user.headers)

    assert response.status_code == 200
    profile = response.json()
    topics = {topic["topic_key"]: topic for topic in profile["topics"]}
    assert topics["python"]["proficiency"] == 75
    assert topics["python"]["source"] == "resume"
    assert topics["sql"]["proficiency"] == 50
    assert topics["docker"]["proficiency"] == 40
    assert profile["unmatched_skills"] == []


async def test_analysis_returns_gaps_and_readiness(api_user: ApiUser) -> None:
    """Совместный анализ считает разрывы и готовность к вакансии."""
    vacancy = await _create_vacancy(api_user)
    resume = await _create_resume(api_user)

    response = await api_user.client.post(
        "/analysis",
        json={"vacancy_id": vacancy["id"], "resume_id": resume["id"]},
        headers=api_user.headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["vacancy"]["id"] == vacancy["id"]
    assert body["resume"]["id"] == resume["id"]

    gaps = {item["skill_name"]: item for item in body["gaps"]["items"]}
    assert gaps["Python"]["satisfied"] is True
    assert gaps["Python"]["user_level"] == 75
    # PostgreSQL — отдельный навык: знаний SQL недостаточно для зачёта.
    assert gaps["PostgreSQL"]["gap"] == 60
    assert gaps["PostgreSQL"]["satisfied"] is False
    assert gaps["Kafka"]["topic_key"] == "kafka"
    assert body["gaps"]["unmatched_count"] == 0
    # (1.0 * 75/70 + 0.8 * 0/60 + 0.3 * 0/40) / 2.1
    assert body["gaps"]["overall_readiness"] == pytest.approx(0.476, abs=0.001)
    assert body["gaps"]["coverage_all"] == pytest.approx(0.476, abs=0.001)
    assert body["gaps"]["confirmed_readiness"] == pytest.approx(0.476, abs=0.001)
    assert body["gaps"]["provisional_count"] == 0
    assert body["gaps"]["provisional_weight"] == 0
    assert body["gaps"]["confirmed_weight"] == pytest.approx(2.1, abs=0.001)


async def test_documents_are_isolated_by_user(api_user: ApiUser, second_user: ApiUser) -> None:
    """Чужой пользователь не видит документы и анализ."""
    vacancy = await _create_vacancy(api_user)
    resume = await _create_resume(api_user)

    response = await second_user.client.get(
        f"/vacancies/{vacancy['id']}", headers=second_user.headers
    )
    assert response.status_code == 404

    response = await second_user.client.post(
        "/analysis",
        json={"vacancy_id": vacancy["id"], "resume_id": resume["id"]},
        headers=second_user.headers,
    )
    assert response.status_code == 404

    profile = await second_user.client.get("/profile", headers=second_user.headers)
    assert profile.status_code == 200
    assert profile.json()["topics"] == []


async def test_vacancy_and_resume_lists(api_user: ApiUser) -> None:
    """Списки документов отдают сводку без навыков."""
    vacancy = await _create_vacancy(api_user)
    resume = await _create_resume(api_user)

    vacancies = await api_user.client.get("/vacancies", headers=api_user.headers)
    resumes = await api_user.client.get("/resumes", headers=api_user.headers)

    assert vacancies.status_code == 200
    assert [item["id"] for item in vacancies.json()] == [vacancy["id"]]
    assert "raw_text" not in vacancies.json()[0]

    assert resumes.status_code == 200
    assert [item["id"] for item in resumes.json()] == [resume["id"]]


async def test_endpoints_require_authentication(api_user: ApiUser) -> None:
    """Без токена доменные эндпоинты недоступны."""
    response = await api_user.client.post("/vacancies", json={"raw_text": VACANCY_TEXT})
    assert response.status_code == 401

    profile = await api_user.client.get("/profile")
    assert profile.status_code == 401


async def test_empty_vacancy_text_is_rejected(api_user: ApiUser) -> None:
    """Пустой текст вакансии не доходит до модели."""
    response = await api_user.client.post(
        "/vacancies", json={"raw_text": ""}, headers=api_user.headers
    )

    assert response.status_code == 422
    assert api_user.provider.calls == []


async def test_llm_failure_returns_502(api_user: ApiUser) -> None:
    """Недоступность модели — понятная ошибка шлюза, а не 500."""
    api_user.provider.responses.clear()

    response = await api_user.client.post(
        "/vacancies", json={"raw_text": VACANCY_TEXT}, headers=api_user.headers
    )

    assert response.status_code == 502
