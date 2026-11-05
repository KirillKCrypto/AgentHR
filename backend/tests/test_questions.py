"""Банк вопросов: дедупликация, выборка и API."""

from uuid import uuid4

from sqlalchemy import delete, select, update

from app.db.session import async_session_factory
from app.models import Question, Topic
from app.questions.generator import generate_questions
from app.services.questions import add_questions, pick_questions
from tests.conftest import ApiUser, SchemaStubProvider


async def _topic(session, key: str = "python") -> Topic:
    """Тема из засеянной онтологии."""
    topic = await session.scalar(select(Topic).where(Topic.key == key))
    assert topic is not None
    return topic


async def test_add_questions_is_idempotent(seeded_db: None) -> None:
    """Повторное добавление того же вопроса не создаёт дубль."""
    marker = uuid4().hex
    async with async_session_factory() as session:
        topic = await _topic(session)
        questions = [
            {"text": f"Что делает Python? {marker}", "expected_points": ["интерпретатор"]}
        ]
        assert await add_questions(session, topic.id, 3, questions) == 1
        assert await add_questions(session, topic.id, 3, questions) == 0
        await session.commit()

    try:
        async with async_session_factory() as session:
            count = len(
                (
                    await session.scalars(
                        select(Question).where(Question.text.like(f"%{marker}%"))
                    )
                ).all()
            )
        assert count == 1
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Question).where(Question.text.like(f"%{marker}%")))
            await session.commit()


async def test_pick_questions_filters_and_excludes(seeded_db: None) -> None:
    """Выборка уважает сложность и исключает уже показанные вопросы."""
    marker = uuid4().hex
    async with async_session_factory() as session:
        topic = await _topic(session)
        questions = [
            {"text": f"Вопрос {index} {marker}", "expected_points": []} for index in range(3)
        ]
        assert await add_questions(session, topic.id, 3, questions) == 3
        await session.commit()

        picked = await pick_questions(session, topic.id, difficulty=3, limit=10)
        assert len(picked) >= 3
        assert all(item.difficulty == 3 for item in picked)

        excluded = {picked[0].id}
        without = await pick_questions(
            session, topic.id, difficulty=3, limit=10, exclude_ids=excluded
        )
        assert excluded.isdisjoint({item.id for item in without})

    async with async_session_factory() as session:
        await session.execute(delete(Question).where(Question.text.like(f"%{marker}%")))
        await session.commit()


async def test_generate_questions_parses_provider_response(seeded_db: None) -> None:
    """Генератор разбирает структурированный ответ LLM."""
    provider = SchemaStubProvider(
        {
            "interview_questions": {
                "questions": [
                    {"text": "Чем отличается list от tuple?", "expected_points": ["изменяемость"]}
                ]
            }
        }
    )
    async with async_session_factory() as session:
        topic = await _topic(session)

    items = await generate_questions(provider, topic, 3, 1)

    assert len(items) == 1
    assert "tuple" in items[0]["text"]


async def test_questions_api_returns_random_items(api_user: ApiUser) -> None:
    """GET /questions отдаёт вопросы по теме."""
    marker = uuid4().hex
    async with async_session_factory() as session:
        topic = await _topic(session)
        questions = [
            {"text": f"API вопрос {index} {marker}", "expected_points": ["пункт"]}
            for index in range(2)
        ]
        await add_questions(session, topic.id, 3, questions)
        await session.commit()

    try:
        response = await api_user.client.get(
            "/questions",
            params={"topic_key": "python", "difficulty": 3, "limit": 2},
            headers=api_user.headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body) == 2
        assert all(isinstance(item["expected_points"], list) for item in body)
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Question).where(Question.text.like(f"%{marker}%")))
            await session.commit()


async def test_questions_test_api_returns_mixed_difficulty(api_user: ApiUser) -> None:
    """Тест по теме содержит вопросы разной сложности."""
    response = await api_user.client.get(
        "/questions/test",
        params={"topic_key": "python", "count": 10},
        headers=api_user.headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert 5 <= len(body) <= 10
    assert len({item["difficulty"] for item in body}) >= 2


async def test_quiz_api_returns_options_and_grades(api_user: ApiUser) -> None:
    """Тест отдаёт варианты ответа, а проверка считает метрику и разбор."""
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
        json={"topic_key": "python", "count": 10},
        headers=api_user.headers,
    )
    assert started.status_code == 201, started.text
    quiz = started.json()
    assert 5 <= len(quiz["questions"]) <= 10
    assert all(len(question["options"]) == 4 for question in quiz["questions"])
    assert all("correct_option" not in question for question in quiz["questions"])

    answers = [
        {"question_id": question["id"], "selected_option": 0}
        for question in quiz["questions"]
    ]
    graded = await api_user.client.post(
        "/questions/quiz/grade",
        json={"topic_key": "python", "answers": answers},
        headers=api_user.headers,
    )
    assert graded.status_code == 200, graded.text
    result = graded.json()
    assert result["total"] == len(quiz["questions"])
    assert result["correct_count"] == sum(item["is_correct"] for item in result["items"])
    assert 0 <= result["score"] <= 1
    assert result["level"] == round(result["score"] * 100)
    assert all(item["correct_option"] in range(4) for item in result["items"])

    repeated = await api_user.client.post(
        "/questions/quiz",
        json={"topic_key": "python", "count": 10},
        headers=api_user.headers,
    )
    assert repeated.status_code == 409

    saved = await api_user.client.get(
        "/questions/quiz/python/result",
        headers=api_user.headers,
    )
    assert saved.status_code == 200
    assert saved.json()["level"] == result["level"]

    profile = await api_user.client.get("/profile", headers=api_user.headers)
    python = next(
        topic for topic in profile.json()["topics"] if topic["topic_key"] == "python"
    )
    assert python["source"] == "test"
    assert python["proficiency"] == result["level"]

    async with async_session_factory() as session:
        await session.execute(
            update(Question)
            .where(Question.id.in_([question["id"] for question in quiz["questions"]]))
            .values(options=[], correct_option=None, explanation=None)
        )
        await session.commit()
