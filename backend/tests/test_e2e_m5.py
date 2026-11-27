"""Сквозной сценарий M5 на уровне API: профиль → план → тест → интервью → отчёт."""

from tests.conftest import ApiUser

RESUME = {
    "experience_years": 4.0,
    "self_level": "middle",
    "skills": [
        {"name": "Python", "proficiency": 80, "evidence": "Python", "confidence": 0.9},
        {"name": "SQL", "proficiency": 45, "evidence": "SQL", "confidence": 0.5},
        {"name": "Docker", "proficiency": 35, "evidence": "Docker", "confidence": 0.4},
        {"name": "FastAPI", "proficiency": 55, "evidence": "FastAPI", "confidence": 0.6},
        {"name": "Redis", "proficiency": 30, "evidence": "Redis", "confidence": 0.4},
        {"name": "Kafka", "proficiency": 20, "evidence": "Kafka", "confidence": 0.3},
    ],
}

VACANCY = {
    "title": "Backend",
    "company": "Acme",
    "level": "middle",
    "skills": [
        {
            "name": "Python",
            "required_level": 80,
            "weight": 1.0,
            "evidence": "Python",
            "confidence": 0.9,
        },
        {
            "name": "SQL",
            "required_level": 75,
            "weight": 0.8,
            "evidence": "SQL",
            "confidence": 0.8,
        },
        {
            "name": "Docker",
            "required_level": 70,
            "weight": 0.6,
            "evidence": "Docker",
            "confidence": 0.7,
        },
    ],
}


async def test_full_user_journey(api_user: ApiUser) -> None:
    """Пользователь проходит весь путь и данные остаются согласованными."""
    api_user.provider.responses["resume_skills"] = RESUME
    resume = await api_user.client.post(
        "/resumes",
        json={"title": "Резюме", "raw_text": "Python SQL Docker FastAPI Redis Kafka"},
        headers=api_user.headers,
    )
    assert resume.status_code == 201, resume.text

    api_user.provider.responses["vacancy_requirements"] = VACANCY
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "Python SQL Docker"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text
    vacancy_id = vacancy.json()["id"]

    plan = await api_user.client.post(
        "/plans",
        json={"vacancy_id": vacancy_id},
        headers=api_user.headers,
    )
    assert plan.status_code == 201, plan.text
    plan_body = plan.json()
    assert 5 <= len(plan_body["items"]) <= 12
    assert "other-auto-review" not in {item["topic_key"] for item in plan_body["items"]}

    api_user.provider.responses["interview_questions"] = {
        "questions": [
            {
                "text": "Как работает индекс в базе данных?",
                "expected_points": ["структура", "поиск", "запись"],
            }
        ]
    }
    api_user.provider.responses["quiz_options"] = {
        "items": [
            {
                "number": number,
                "options": ["Вариант A", "Вариант B", "Вариант C", "Вариант D"],
                "correct_index": 0,
                "explanation": "A",
            }
            for number in range(1, 11)
        ]
    }
    quiz = await api_user.client.post(
        "/questions/quiz",
        json={"topic_key": "python", "count": 10},
        headers=api_user.headers,
    )
    assert quiz.status_code == 201, quiz.text
    quiz_body = quiz.json()
    assert len(quiz_body["questions"]) >= 5
    graded = await api_user.client.post(
        "/questions/quiz/grade",
        json={
            "topic_key": "python",
            "answers": [
                {"question_id": item["id"], "selected_option": 0}
                for item in quiz_body["questions"]
            ],
        },
        headers=api_user.headers,
    )
    assert graded.status_code == 200, graded.text
    assert graded.json()["total"] == len(quiz_body["questions"])

    api_user.provider.responses["interview_evaluation"] = {
        "score": 80,
        "feedback_brief": "Ответ по существу.",
    }
    interview = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy_id},
        headers=api_user.headers,
    )
    assert interview.status_code == 201, interview.text
    session = interview.json()
    assert session["answer_seconds"] == 300
    assert session["turns"][0]["deadline_at"]

    for _ in range(16):
        if session["status"] == "completed":
            break
        turn = next(
            (item for item in session["turns"] if item["status"] == "pending"),
            None,
        )
        if turn is None:
            break
        answer = await api_user.client.post(
            f"/interviews/{session['id']}/answers",
            json={
                "turn_id": turn["id"],
                "answer_text": "Ответ по существу вопроса.",
                "answer_mode": "text",
            },
            headers=api_user.headers,
        )
        assert answer.status_code == 200, answer.text
        session = answer.json()["session"]
    assert session["status"] == "completed"

    report = await api_user.client.get(
        f"/interviews/{session['id']}/report",
        headers=api_user.headers,
    )
    assert report.status_code == 200, report.text
    assert report.json()["answered_count"] >= 1

    dashboard = await api_user.client.get("/dashboard", headers=api_user.headers)
    assert dashboard.status_code == 200, dashboard.text
    dashboard_body = dashboard.json()
    assert dashboard_body["vacancy"]["id"] == vacancy_id
    assert dashboard_body["plan"]["id"] == plan_body["id"]
    assert dashboard_body["last_interview"]["id"] == session["id"]
    assert dashboard_body["activity"]["interviews_completed"] == 1
    assert dashboard_body["tests"]["completed_count"] == 1
