"""Интервью: сценарий из плана, ответы, SSE и обновление профиля."""

from tests.conftest import ApiUser

RESUME_DATA = {
    "experience_years": 3.0,
    "self_level": "middle",
    "skills": [
        {"name": "Python", "proficiency": 80, "confidence": 0.8, "evidence": "python"},
        {"name": "SQL", "proficiency": 70, "confidence": 0.8, "evidence": "sql"},
        {"name": "Docker", "proficiency": 60, "confidence": 0.7, "evidence": "docker"},
        {"name": "FastAPI", "proficiency": 60, "confidence": 0.7, "evidence": "fastapi"},
        {"name": "Redis", "proficiency": 50, "confidence": 0.6, "evidence": "redis"},
        {"name": "Kafka", "proficiency": 40, "confidence": 0.6, "evidence": "kafka"},
    ],
}


async def _create_plan(api_user: ApiUser) -> str:
    """Создаёт резюме и план, возвращает id плана."""
    api_user.provider.responses["resume_skills"] = RESUME_DATA
    resume = await api_user.client.post(
        "/resumes",
        json={"title": "Резюме", "raw_text": "Python SQL Docker FastAPI Redis Kafka"},
        headers=api_user.headers,
    )
    assert resume.status_code == 201, resume.text
    plan = await api_user.client.post("/plans", json={}, headers=api_user.headers)
    assert plan.status_code == 201, plan.text
    return plan.json()["id"]


async def test_interview_flow_updates_profile(api_user: ApiUser) -> None:
    """Интервью проходит вопросы и обновляет профиль после последнего ответа."""
    plan_id = await _create_plan(api_user)
    api_user.provider.responses["interview_evaluation"] = {
        "score": 80,
        "verdict": "strong",
        "covered_points": ["основная мысль"],
        "missed_points": ["деталь"],
        "feedback_brief": "Ответ хороший.",
    }

    created = await api_user.client.post(
        "/interviews",
        json={"plan_id": plan_id},
        headers=api_user.headers,
    )
    assert created.status_code == 201, created.text
    interview = created.json()
    assert interview["status"] == "in_progress"
    assert 1 <= interview["question_count"] <= 8
    assert len(interview["turns"]) == interview["question_count"]

    first = interview["turns"][0]
    answered = await api_user.client.post(
        f"/interviews/{interview['id']}/answers",
        json={"turn_id": first["id"], "answer_text": "Развёрнутый ответ на вопрос."},
        headers=api_user.headers,
    )
    assert answered.status_code == 200, answered.text
    outcome = answered.json()
    assert outcome["turn"]["score"] == 80
    assert outcome["turn"]["status"] == "answered"

    repeated = await api_user.client.post(
        f"/interviews/{interview['id']}/answers",
        json={"turn_id": first["id"], "answer_text": "Ещё раз."},
        headers=api_user.headers,
    )
    assert repeated.status_code == 409

    current = interview
    for turn in current["turns"][1:]:
        response = await api_user.client.post(
            f"/interviews/{current['id']}/answers",
            json={"turn_id": turn["id"], "answer_text": "Ответ по существу вопроса."},
            headers=api_user.headers,
        )
        assert response.status_code == 200, response.text
        current = response.json()["session"]

    final = await api_user.client.get(
        f"/interviews/{interview['id']}",
        headers=api_user.headers,
    )
    assert final.status_code == 200
    body = final.json()
    assert body["status"] == "completed"
    assert body["level"] == 80

    profile = await api_user.client.get("/profile", headers=api_user.headers)
    topics = {topic["topic_key"]: topic for topic in profile.json()["topics"]}
    assert topics["python"]["source"] == "interview"


async def test_interview_stream_returns_events(api_user: ApiUser) -> None:
    """SSE-эндпоинт отдаёт оценку, токены фидбека и завершение."""
    plan_id = await _create_plan(api_user)
    api_user.provider.responses["interview_evaluation"] = {
        "score": 70,
        "verdict": "partial",
        "covered_points": [],
        "missed_points": ["деталь"],
        "feedback_brief": "Нужно подробнее.",
    }
    api_user.provider.responses["interview_feedback"] = "Хороший ответ, но добавь детали."

    created = await api_user.client.post(
        "/interviews",
        json={"plan_id": plan_id},
        headers=api_user.headers,
    )
    assert created.status_code == 201, created.text
    interview = created.json()
    turn = interview["turns"][0]

    response = await api_user.client.post(
        f"/interviews/{interview['id']}/answers/stream",
        json={"turn_id": turn["id"], "answer_text": "Ответ по существу вопроса."},
        headers=api_user.headers,
    )

    assert response.status_code == 200, response.text
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: evaluation" in response.text
    assert "event: token" in response.text
    assert "event: done" in response.text
    assert "Хороший ответ" in response.text
