"""Дашборд и живой прогресс плана."""

from tests.conftest import ApiUser


async def test_plan_progress_uses_best_test_score(api_user: ApiUser) -> None:
    """Прогресс плана считается по тестам, а не по резюме."""
    api_user.provider.responses["resume_skills"] = {
        "experience_years": 3.0,
        "self_level": "middle",
        "skills": [
            {"name": name, "proficiency": level, "evidence": name, "confidence": 0.8}
            for name, level in [
                ("Python", 90),
                ("SQL", 80),
                ("Docker", 70),
                ("FastAPI", 60),
                ("Redis", 50),
                ("Kafka", 40),
            ]
        ],
    }
    resume = await api_user.client.post(
        "/resumes",
        json={"title": "Резюме", "raw_text": "Python SQL Docker FastAPI Redis Kafka"},
        headers=api_user.headers,
    )
    assert resume.status_code == 201, resume.text
    plan = await api_user.client.post("/plans", json={}, headers=api_user.headers)
    assert plan.status_code == 201, plan.text
    plan_body = plan.json()
    topic = plan_body["items"][0]

    before = await api_user.client.get(
        f"/plans/{plan_body['id']}/progress",
        headers=api_user.headers,
    )
    assert before.status_code == 200, before.text
    assert before.json()["progress"] == 0

    api_user.provider.responses["interview_questions"] = {
        "questions": [
            {
                "text": f"Вопрос по теме {topic['topic_name']}",
                "expected_points": ["пункт"],
            }
        ]
    }
    api_user.provider.responses["quiz_options"] = {
        "items": [
            {
                "number": number,
                "options": ["Вариант A", "Вариант B", "Вариант C", "Вариант D"],
                "correct_index": 0,
                "explanation": "A — правильный ответ",
            }
            for number in range(1, 11)
        ]
    }
    started = await api_user.client.post(
        "/questions/quiz",
        json={"topic_key": topic["topic_key"], "count": 10},
        headers=api_user.headers,
    )
    assert started.status_code == 201, started.text
    answers = [
        {"question_id": question["id"], "selected_option": 0}
        for question in started.json()["questions"]
    ]
    graded = await api_user.client.post(
        "/questions/quiz/grade",
        json={"topic_key": topic["topic_key"], "answers": answers},
        headers=api_user.headers,
    )
    assert graded.status_code == 200, graded.text
    test_result = graded.json()

    progress = await api_user.client.get(
        f"/plans/{plan_body['id']}/progress",
        headers=api_user.headers,
    )
    assert progress.status_code == 200, progress.text
    body = progress.json()
    expected = round(test_result["score"] / len(plan_body["items"]), 3)
    assert body["progress"] == expected
    assert body["tests_completed"] == 1
    assert body["attempts_count"] == 1
    item = next(
        entry for entry in body["items"] if entry["topic_id"] == topic["topic_id"]
    )
    assert item["progress"] == test_result["score"]
    assert item["test_level"] == test_result["level"]
    assert item["status"] in {"partial", "confirmed"}


async def test_vacancy_metrics_split_potential_and_verified(
    api_user: ApiUser,
) -> None:
    """Готовность показывает потенциал, подтверждение и очередь проверки."""
    api_user.provider.responses["resume_skills"] = {
        "experience_years": 3.0,
        "self_level": "middle",
        "skills": [
            {"name": "Python", "proficiency": 90, "evidence": "Python", "confidence": 0.9},
            {"name": "SQL", "proficiency": 60, "evidence": "SQL", "confidence": 0.6},
            {"name": "Docker", "proficiency": 50, "evidence": "Docker", "confidence": 0.6},
        ],
    }
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": "Python",
                "required_level": 70,
                "weight": 1.0,
                "evidence": "Python",
                "confidence": 0.9,
                "criticality": "must_have",
            },
            {
                "name": "SQL",
                "required_level": 70,
                "weight": 0.8,
                "evidence": "SQL",
                "confidence": 0.8,
                "criticality": "must_have",
            },
            {
                "name": "Docker",
                "required_level": 60,
                "weight": 0.4,
                "evidence": "Docker",
                "confidence": 0.6,
                "criticality": "nice_to_have",
            },
        ],
    }
    resume = await api_user.client.post(
        "/resumes",
        json={"title": "Резюме", "raw_text": "Python SQL"},
        headers=api_user.headers,
    )
    assert resume.status_code == 201, resume.text
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "Python SQL Docker"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text

    gaps = await api_user.client.get(
        f"/profile/gaps?vacancy_id={vacancy.json()['id']}",
        headers=api_user.headers,
    )
    assert gaps.status_code == 200, gaps.text
    body = gaps.json()
    assert body["potential_readiness"] > 0
    assert body["verified_readiness"] == 0
    assert body["evidence_coverage"] == 0
    assert body["band"] == "needs_confirmation"
    assert body["confirmation_queue"]
    assert all(item["verified_level"] == 0 for item in body["items"])


async def test_dashboard_and_plan_progress(api_user: ApiUser) -> None:
    """Дашборд отдаёт готовность, план и последнее интервью."""
    api_user.provider.responses["resume_skills"] = {
        "experience_years": 3.0,
        "self_level": "middle",
        "skills": [
            {"name": "Python", "proficiency": 80, "evidence": "Python", "confidence": 0.9},
            {"name": "SQL", "proficiency": 40, "evidence": "SQL", "confidence": 0.5},
        ],
    }
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": "Python",
                "required_level": 70,
                "weight": 1.0,
                "evidence": "Python",
                "confidence": 0.9,
            },
            {
                "name": "SQL",
                "required_level": 70,
                "weight": 0.8,
                "evidence": "SQL",
                "confidence": 0.8,
            },
        ],
    }
    resume = await api_user.client.post(
        "/resumes",
        json={"title": "Резюме", "raw_text": "Python SQL"},
        headers=api_user.headers,
    )
    assert resume.status_code == 201, resume.text
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "Python SQL"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text
    plan = await api_user.client.post(
        "/plans",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    assert plan.status_code == 201, plan.text

    dashboard = await api_user.client.get("/dashboard", headers=api_user.headers)
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert body["profile"]["topics_count"] >= 2
    assert body["vacancy"]["id"] == vacancy.json()["id"]
    assert body["vacancy"]["coverage"] <= 1
    assert body["plan"]["id"] == plan.json()["id"]
    assert 0 <= body["plan"]["progress"] <= 1

    progress = await api_user.client.get(
        f"/plans/{plan.json()['id']}/progress",
        headers=api_user.headers,
    )
    assert progress.status_code == 200, progress.text
    progress_body = progress.json()
    assert progress_body["topics_total"] >= 1
    assert progress_body["items"]
    assert all(0 <= item["progress"] <= 1 for item in progress_body["items"])

    api_user.provider.responses["interview_evaluation"] = {
        "score": 80,
        "feedback_brief": "Ответ хороший.",
    }
    interview = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    assert interview.status_code == 201, interview.text
    current = interview.json()

    active_dashboard = await api_user.client.get("/dashboard", headers=api_user.headers)
    active = active_dashboard.json()["active_interview"]
    assert active["id"] == current["id"]
    assert active["answered_count"] == 0

    for _ in range(16):
        if current["status"] == "completed":
            break
        turn = next(
            (item for item in current["turns"] if item["status"] == "pending"),
            None,
        )
        if turn is None:
            break
        answer = await api_user.client.post(
            f"/interviews/{current['id']}/answers",
            json={"turn_id": turn["id"], "answer_text": "Ответ по существу."},
            headers=api_user.headers,
        )
        assert answer.status_code == 200, answer.text
        current = answer.json()["session"]
    assert current["status"] == "completed"

    dashboard = await api_user.client.get("/dashboard", headers=api_user.headers)
    body = dashboard.json()
    assert body["last_interview"]["id"] == current["id"]
    assert body["last_interview"]["score"] == 80
    assert body["activity"]["interviews_completed"] == 1
    assert len(body["interview_history"]) == 1

    report = await api_user.client.get(
        f"/interviews/{current['id']}/report",
        headers=api_user.headers,
    )
    assert report.status_code == 200, report.text
    report_body = report.json()
    assert report_body["vacancy_id"] == vacancy.json()["id"]
    assert report_body["question_count"] >= 1
    assert report_body["answered_count"] >= 1
