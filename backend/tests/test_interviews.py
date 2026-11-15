"""Интервью: сценарий из плана, ответы, SSE и обновление профиля."""

from app.services.interview import _difficulties_for_level, _verdict_for
from app.services.vacancy_level import normalize_level
from tests.conftest import ApiUser


def test_verdict_consistency() -> None:
    """Вердикт соответствует числовой оценке."""
    assert _verdict_for(85) == "strong"
    assert _verdict_for(75) == "partial"
    assert _verdict_for(49) == "weak"


def test_difficulty_sequences_follow_vacancy_level() -> None:
    """Junior/middle не выше 3, senior/lead с упором на 3–5."""
    assert normalize_level("Senior Python") == "senior"
    assert normalize_level("Junior") == "junior"
    assert normalize_level("middle") == "middle"
    assert normalize_level("Lead") == "lead"
    assert normalize_level(None) is None

    junior = _difficulties_for_level("junior_middle")
    assert junior is not None
    assert all(difficulty <= 3 for difficulty in junior)

    senior = _difficulties_for_level("senior_lead")
    assert senior is not None
    assert max(senior) == 5
    assert sum(1 for difficulty in senior if 3 <= difficulty <= 5) >= 6
    assert _difficulties_for_level(None) is None


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


async def _create_vacancy(api_user: ApiUser) -> str:
    """Создаёт вакансию с темами для интервью."""
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": name,
                "required_level": 70,
                "weight": 1.0,
                "evidence": name,
                "confidence": 0.9,
            }
            for name in ("Python", "SQL", "Docker", "FastAPI", "Redis", "Kafka")
        ],
    }
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "Python SQL Docker FastAPI Redis Kafka"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text
    return vacancy.json()["id"]


def _set_evaluation(
    api_user: ApiUser,
    score: float,
    *,
    missed_points: list[str] | None = None,
) -> None:
    """Задаёт ответ LLM на оценку следующего ответа."""
    api_user.provider.responses["interview_evaluation"] = {
        "score": score,
        "verdict": "strong" if score >= 80 else "weak",
        "covered_points": ["основная мысль"],
        "missed_points": missed_points if missed_points is not None else ["деталь"],
        "feedback_brief": "Ответ оценён.",
    }


async def _drive_interview(api_user: ApiUser, session: dict) -> dict:
    """Отвечает на все вопросы, пока интервью не завершится."""
    for _ in range(16):
        if session["status"] == "completed":
            break
        turn = next(
            (item for item in session["turns"] if item["status"] == "pending"),
            None,
        )
        if turn is None:
            break
        response = await api_user.client.post(
            f"/interviews/{session['id']}/answers",
            json={"turn_id": turn["id"], "answer_text": "Ответ по существу вопроса."},
            headers=api_user.headers,
        )
        assert response.status_code == 200, response.text
        session = response.json()["session"]
    return session


async def test_interview_generates_missing_question(api_user: ApiUser) -> None:
    """Тема без вопросов в банке получает лениво сгенерированный вопрос."""
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": "CustomFramework",
                "required_level": 70,
                "weight": 1.0,
                "evidence": "CustomFramework в проде",
                "confidence": 0.9,
            }
        ],
    }
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "CustomFramework"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text
    api_user.provider.responses["interview_questions"] = {
        "questions": [
            {
                "text": "Как устроен жизненный цикл CustomFramework?",
                "expected_points": ["инициализация", "обновление", "завершение"],
            }
        ]
    }

    created = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["question_count"] == 1


async def test_interview_requires_vacancy(api_user: ApiUser) -> None:
    """Интервью по плану больше не создаётся: нужен vacancy_id."""
    response = await api_user.client.post(
        "/interviews",
        json={"plan_id": "00000000-0000-0000-0000-000000000001"},
        headers=api_user.headers,
    )

    assert response.status_code == 422


async def test_interview_flow_updates_profile(api_user: ApiUser) -> None:
    """Интервью проходит вопросы и обновляет профиль после последнего ответа."""
    vacancy_id = await _create_vacancy(api_user)
    api_user.provider.responses["interview_evaluation"] = {
        "score": 80,
        "verdict": "strong",
        "covered_points": ["основная мысль"],
        "missed_points": ["деталь"],
        "feedback_brief": "Ответ хороший.",
    }

    created = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy_id},
        headers=api_user.headers,
    )
    assert created.status_code == 201, created.text
    interview = created.json()
    assert interview["status"] == "in_progress"
    assert interview["question_count"] == 1
    assert len(interview["turns"]) == 1
    assert interview["max_questions"] == 8

    listing = await api_user.client.get("/interviews", headers=api_user.headers)
    assert listing.status_code == 200
    summary = listing.json()[0]
    assert summary["vacancy_id"] == vacancy_id
    assert summary["max_questions"] == 8
    assert summary["answered_count"] == 0

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
    assert outcome["next_turn"] is not None

    repeated = await api_user.client.post(
        f"/interviews/{interview['id']}/answers",
        json={"turn_id": first["id"], "answer_text": "Ещё раз."},
        headers=api_user.headers,
    )
    assert repeated.status_code == 409

    current = await _drive_interview(api_user, outcome["session"])

    final = await api_user.client.get(
        f"/interviews/{interview['id']}",
        headers=api_user.headers,
    )
    assert final.status_code == 200
    body = final.json()
    assert body["status"] == "completed"
    assert body["level"] == 80
    assert current["status"] == "completed"

    profile = await api_user.client.get("/profile", headers=api_user.headers)
    topics = {topic["topic_key"]: topic for topic in profile.json()["topics"]}
    assert topics["python"]["source"] == "interview"


async def test_vacancy_interview_uses_vacancy_topics(api_user: ApiUser) -> None:
    """Интервью по вакансии строится из её требований."""
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": "Python",
                "required_level": 80,
                "weight": 1.0,
                "evidence": "Python в проде",
                "confidence": 0.9,
            },
            {
                "name": "SQL",
                "required_level": 70,
                "weight": 0.8,
                "evidence": "SQL-запросы",
                "confidence": 0.8,
            },
        ],
    }
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "Python SQL"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text

    interview = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )

    assert interview.status_code == 201, interview.text
    body = interview.json()
    assert body["vacancy_id"] == vacancy.json()["id"]
    assert body["question_count"] == 1
    assert body["turns"][0]["topic_key"] in {"python", "sql"}
    assert body["turns"][0]["context"]
    assert vacancy.json()["level"] == "middle"

    _set_evaluation(api_user, 80)
    final = await _drive_interview(api_user, body)
    assert {turn["topic_key"] for turn in final["turns"]} == {"python", "sql"}
    assert all(turn["context"] for turn in final["turns"])
    assert all(turn["difficulty"] <= 3 for turn in final["turns"])


async def test_senior_title_overrides_wrong_llm_level(api_user: ApiUser) -> None:
    """Заголовок Senior важнее ошибочного middle от модели."""
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": name,
                "required_level": 80,
                "weight": 1.0,
                "evidence": f"{name} в проде",
                "confidence": 0.9,
            }
            for name in ("Python", "SQL", "Docker")
        ],
    }
    vacancy = await api_user.client.post(
        "/vacancies",
        json={
            "title": "Senior Python разработчик",
            "raw_text": "Требования: 6+ лет Python, SQL, Docker.",
        },
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text
    assert vacancy.json()["level"] == "senior"

    interview = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    assert interview.status_code == 201, interview.text
    _set_evaluation(api_user, 80)
    final = await _drive_interview(api_user, interview.json())
    difficulties = [turn["difficulty"] for turn in final["turns"]]
    assert 5 in difficulties, difficulties


async def test_interview_report_marks_strengths_and_untouched(
    api_user: ApiUser,
) -> None:
    """Отчёт после финиша делит темы на сильные и незатронутые."""
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
                "required_level": 70,
                "weight": 1.0 - index * 0.02,
                "evidence": f"{name} в проде",
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
        "score": 85,
        "verdict": "strong",
        "covered_points": ["основная мысль"],
        "missed_points": [],
        "feedback_brief": "Ответ хороший.",
    }
    created = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    assert created.status_code == 201, created.text
    interview = created.json()

    early = await api_user.client.get(
        f"/interviews/{interview['id']}/report",
        headers=api_user.headers,
    )
    assert early.status_code == 409

    for _ in range(16):
        response = await api_user.client.post(
            f"/interviews/{interview['id']}/answers",
            json={
                "turn_id": interview["turns"][-1]["id"],
                "answer_text": "Ответ по существу вопроса.",
            },
            headers=api_user.headers,
        )
        assert response.status_code in (200, 409), response.text
        if response.status_code == 409:
            break
        interview = response.json()["session"]
        if interview["status"] == "completed":
            break

    report = await api_user.client.get(
        f"/interviews/{interview['id']}/report",
        headers=api_user.headers,
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["status"] == "completed"
    assert body["strengths"]
    assert body["improvements"] == []
    assert body["untouched"]
    asked = {turn["topic_key"] for turn in interview["turns"]}
    assert all(item["topic_key"] not in asked for item in body["untouched"])


async def test_interview_report_marks_weak_topics(api_user: ApiUser) -> None:
    """Слабые ответы попадают в «что подтянуть» с упущенными пунктами."""
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": "Python",
                "required_level": 70,
                "weight": 1.0,
                "evidence": "Python в проде",
                "confidence": 0.9,
            }
        ],
    }
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "Python"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text

    api_user.provider.responses["interview_evaluation"] = {
        "score": 40,
        "verdict": "weak",
        "covered_points": [],
        "missed_points": ["индексы", "план запроса"],
        "feedback_brief": "Нужно подробнее.",
    }
    created = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    interview = created.json()
    final = await _drive_interview(api_user, interview)

    report = await api_user.client.get(
        f"/interviews/{final['id']}/report",
        headers=api_user.headers,
    )
    body = report.json()
    assert body["strengths"] == []
    assert body["improvements"]
    assert body["improvements"][0]["score"] == 40
    assert "индексы" in body["improvements"][0]["missed_points"]


async def test_interview_stream_returns_events(api_user: ApiUser) -> None:
    """SSE-эндпоинт отдаёт оценку, токены фидбека и завершение."""
    vacancy_id = await _create_vacancy(api_user)
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
        json={"vacancy_id": vacancy_id},
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


async def test_strong_answer_increases_difficulty(api_user: ApiUser) -> None:
    """Сильный ответ повышает сложность следующего вопроса на шаг."""
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "senior",
        "skills": [
            {
                "name": name,
                "required_level": 70,
                "weight": 1.0,
                "evidence": name,
                "confidence": 0.9,
            }
            for name in ("Python", "SQL", "Docker")
        ],
    }
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Senior Backend", "raw_text": "Python SQL Docker"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text
    api_user.provider.responses["interview_questions"] = {
        "questions": [
            {
                "text": "Как устроена изоляция транзакций в PostgreSQL?",
                "expected_points": ["уровни изоляции", "MVCC", "аномалии"],
            }
        ]
    }
    _set_evaluation(api_user, 90, missed_points=[])

    created = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    interview = created.json()
    assert interview["turns"][0]["difficulty"] == 1

    final = await _drive_interview(api_user, interview)
    difficulties = [turn["difficulty"] for turn in final["turns"]]
    assert difficulties[1] == 4, difficulties
    assert max(difficulties) <= 5, difficulties


async def test_weak_answer_adds_follow_up(api_user: ApiUser) -> None:
    """Слабый ответ создаёт уточняющий вопрос по той же теме."""
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
            }
        ],
    }
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "Python"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text
    _set_evaluation(api_user, 40, missed_points=["индексы", "план запроса"])

    created = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    interview = created.json()
    final = await _drive_interview(api_user, interview)

    follow_ups = [turn for turn in final["turns"] if turn["kind"] == "follow_up"]
    assert len(follow_ups) == 1
    assert follow_ups[0]["parent_turn_id"] == final["turns"][0]["id"]
    assert follow_ups[0]["topic_key"] == final["turns"][0]["topic_key"]


async def test_follow_up_limit_is_enforced(api_user: ApiUser) -> None:
    """Не больше двух уточнений за сессию и одного на тему."""
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Backend",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": name,
                "required_level": 70,
                "weight": 1.0,
                "evidence": name,
                "confidence": 0.9,
            }
            for name in ("Python", "SQL", "Docker")
        ],
    }
    vacancy = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": "Python SQL Docker"},
        headers=api_user.headers,
    )
    assert vacancy.status_code == 201, vacancy.text
    _set_evaluation(api_user, 40, missed_points=["деталь"])

    created = await api_user.client.post(
        "/interviews",
        json={"vacancy_id": vacancy.json()["id"]},
        headers=api_user.headers,
    )
    final = await _drive_interview(api_user, created.json())

    follow_ups = [turn for turn in final["turns"] if turn["kind"] == "follow_up"]
    assert len(follow_ups) <= 2
    topics = [turn["topic_id"] for turn in follow_ups]
    assert len(topics) == len(set(topics))
