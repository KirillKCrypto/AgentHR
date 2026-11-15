"""Планы подготовки: выбор тем из резюме и API."""

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
    """План берёт самые слабые темы профиля, а не самые сильные."""
    await _create_resume(api_user)

    response = await api_user.client.post("/plans", json={}, headers=api_user.headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["vacancy_id"] is None
    assert 5 <= len(body["items"]) <= 12
    assert body["items"][0]["topic_key"] == "kafka"
    assert body["items"][0]["current_level"] == 40
    assert "низкий уровень в профиле" in body["items"][0]["reason"]
    assert all(item["target_level"] == 100 for item in body["items"])
    keys = [item["topic_key"] for item in body["items"]]
    assert keys.index("kafka") < keys.index("python")

    repeated = await api_user.client.post("/plans", json={}, headers=api_user.headers)
    assert repeated.status_code == 200
    assert repeated.json()["id"] == body["id"]
    assert repeated.json()["reused"] is True


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
    redis = body["items"][0]
    assert redis["topic_key"] == "redis"
    assert redis["target_level"] == 80
    assert "разрыв 30" in redis["reason"]
    assert "требуется 80%" in redis["reason"]
    assert body["vacancy_title"] == "Backend"


async def test_plans_are_bound_to_vacancy(api_user: ApiUser) -> None:
    """План по другой вакансии не переиспользуется."""
    await _create_resume(api_user)

    async def create_vacancy(title: str, skill: str) -> str:
        api_user.provider.responses["vacancy_requirements"] = {
            "title": title,
            "company": "Acme",
            "level": "middle",
            "skills": [
                {
                    "name": skill,
                    "required_level": 80,
                    "weight": 1.0,
                    "evidence": skill,
                    "confidence": 0.9,
                }
            ],
        }
        response = await api_user.client.post(
            "/vacancies",
            json={"title": title, "raw_text": f"Нужен {skill}"},
            headers=api_user.headers,
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    first_vacancy = await create_vacancy("Backend Redis", "Redis")
    first = await api_user.client.post(
        "/plans",
        json={"vacancy_id": first_vacancy},
        headers=api_user.headers,
    )
    assert first.status_code == 201, first.text

    second_vacancy = await create_vacancy("Backend Kafka", "Kafka")
    second = await api_user.client.post(
        "/plans",
        json={"vacancy_id": second_vacancy},
        headers=api_user.headers,
    )
    assert second.status_code == 201, second.text
    assert second.json()["id"] != first.json()["id"]
    assert second.json()["vacancy_id"] == second_vacancy
    assert second.json()["items"][0]["topic_key"] == "kafka"

    repeated = await api_user.client.post(
        "/plans",
        json={"vacancy_id": second_vacancy},
        headers=api_user.headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["id"] == second.json()["id"]
    assert repeated.json()["reused"] is True


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


async def test_plan_uses_interview_weak_and_untouched_topics(
    api_user: ApiUser,
) -> None:
    """План после интервью подтягивает слабые и незатронутые темы вакансии."""
    await _create_resume(api_user)
    names = [
        "Python",
        "SQL",
        "Docker",
        "FastAPI",
        "Redis",
        "Kafka",
        "PostgreSQL",
        "Git",
        "Linux",
        "REST",
    ]
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": name,
                "required_level": 80,
                "weight": 1.0 - index * 0.02,
                "evidence": name,
                "confidence": 0.9,
            }
            for index, name in enumerate(names)
        ],
    }
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "Backend"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text

    api_user.provider.responses["interview_evaluation"] = {
        "score": 40,
        "verdict": "weak",
        "covered_points": [],
        "missed_points": ["деталь"],
        "feedback_brief": "Слабо.",
    }
    interview_response = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    interview = interview_response.json()
    for _ in range(16):
        if interview["status"] == "completed":
            break
        turn = next(
            (item for item in interview["turns"] if item["status"] == "pending"),
            None,
        )
        if turn is None:
            break
        answer = await api_user.client.post(
            f"/interviews/{interview['id']}/answers",
            json={"turn_id": turn["id"], "answer_text": "Короткий ответ."},
            headers=api_user.headers,
        )
        assert answer.status_code == 200, answer.text
        interview = answer.json()["session"]
    assert interview["status"] == "completed"

    plan = await api_user.client.post(
        "/plans",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    assert plan.status_code == 201, plan.text
    reasons = [item["reason"] for item in plan.json()["items"]]

    assert any("слабый ответ в интервью" in reason for reason in reasons)
    assert any("не затронуто в интервью" in reason for reason in reasons)
