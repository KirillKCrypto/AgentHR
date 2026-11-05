"""Мини-тесты навыков: банк, прохождение и verified level."""

from uuid import UUID

from sqlalchemy import func, select

from app.assessment.seed import seed_assessment_questions
from app.db.session import async_session_factory
from app.models import AssessmentQuestion, UserSkillState
from tests.conftest import ApiUser


async def _correct_keys(question_ids: list[str]) -> dict[str, str]:
    """Правильные ответы для вопросов попытки (тестовая инспекция БД)."""
    async with async_session_factory() as session:
        questions = (
            await session.scalars(
                select(AssessmentQuestion).where(
                    AssessmentQuestion.id.in_([UUID(value) for value in question_ids])
                )
            )
        ).all()
    return {str(question.id): question.correct_key for question in questions}


async def test_assessment_topics_are_available(api_user: ApiUser) -> None:
    """Банк вопросов отдаёт доступные темы."""
    response = await api_user.client.get("/assessments/topics", headers=api_user.headers)
    assert response.status_code == 200, response.text
    topics = {item["topic_key"]: item for item in response.json()}
    assert topics["python"]["question_count"] == 20
    assert topics["sql"]["question_count"] == 20


async def test_assessment_updates_verified_level(api_user: ApiUser) -> None:
    """Правильные ответы дают verified level и источник assessment."""
    start = await api_user.client.post(
        "/assessments/python/start",
        headers=api_user.headers,
    )
    assert start.status_code == 200, start.text
    body = start.json()
    attempt_id = body["attempt_id"]
    question_ids = [question["id"] for question in body["questions"]]
    keys = await _correct_keys(question_ids)

    for question_id in question_ids:
        response = await api_user.client.post(
            f"/assessments/{attempt_id}/answers",
            json={"question_id": question_id, "answer_key": keys[question_id]},
            headers=api_user.headers,
        )
        assert response.status_code == 200, response.text

    finish = await api_user.client.post(
        f"/assessments/{attempt_id}/finish",
        headers=api_user.headers,
    )
    assert finish.status_code == 200, finish.text
    result = finish.json()
    assert result["test_level"] == 95
    assert result["correct_count"] == 10
    assert result["total"] == 10

    profile = await api_user.client.get("/profile", headers=api_user.headers)
    assert profile.status_code == 200
    topics = {topic["topic_key"]: topic for topic in profile.json()["topics"]}
    assert topics["python"]["verified_level"] == 95
    assert topics["python"]["proficiency"] == 95
    assert topics["python"]["source"] == "assessment"

    restart = await api_user.client.post("/assessments/python/start", headers=api_user.headers)
    assert restart.status_code == 409

    available = await api_user.client.get("/assessments/topics", headers=api_user.headers)
    python_topic = next(item for item in available.json() if item["topic_key"] == "python")
    assert python_topic["completed"] is True
    assert python_topic["test_level"] == 95


async def test_wrong_answers_give_low_level(api_user: ApiUser) -> None:
    """Неправильные ответы не поднимают verified level."""
    start = await api_user.client.post("/assessments/git/start", headers=api_user.headers)
    assert start.status_code == 200, start.text
    body = start.json()
    attempt_id = body["attempt_id"]
    keys = await _correct_keys([question["id"] for question in body["questions"]])

    for question in body["questions"]:
        wrong = next(
            option["key"] for option in question["options"] if option["key"] != keys[question["id"]]
        )
        response = await api_user.client.post(
            f"/assessments/{attempt_id}/answers",
            json={"question_id": question["id"], "answer_key": wrong},
            headers=api_user.headers,
        )
        assert response.status_code == 200, response.text

    finish = await api_user.client.post(
        f"/assessments/{attempt_id}/finish",
        headers=api_user.headers,
    )
    assert finish.status_code == 200, finish.text
    assert finish.json()["test_level"] == 20

    async with async_session_factory() as session:
        state = await session.scalar(
            select(UserSkillState).where(
                UserSkillState.user_id == UUID(api_user.user_id),
                UserSkillState.topic_id
                == (
                    await session.scalar(
                        select(AssessmentQuestion.topic_id).where(
                            AssessmentQuestion.key == "git-20"
                        )
                    )
                ),
            )
        )
    assert state is not None
    assert state.verified_level == 20


async def test_assessment_seed_is_idempotent(seeded_db: None) -> None:
    """Повторный сид не дублирует вопросы."""
    async with async_session_factory() as session:
        before = await session.scalar(select(func.count()).select_from(AssessmentQuestion))
        await seed_assessment_questions(session)
        after = await session.scalar(select(func.count()).select_from(AssessmentQuestion))
    assert before == 160
    assert after == 160
