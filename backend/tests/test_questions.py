"""Банк вопросов: дедупликация, выборка и API."""

from uuid import uuid4

from sqlalchemy import delete, select

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
        assert body[0]["expected_points"] == ["пункт"]
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Question).where(Question.text.like(f"%{marker}%")))
            await session.commit()
