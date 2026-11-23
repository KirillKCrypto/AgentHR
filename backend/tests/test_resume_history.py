"""История резюме, активное резюме и защита от дублей."""

from uuid import uuid4

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models import Resume, Topic, User, UserSkillState
from app.services.analysis import ExtractedSkill, ResumeProfile
from app.services.plans import create_plan, get_plan, list_plans
from app.services.profile import (
    activate_resume,
    clear_resumes,
    delete_resume,
    get_profile,
    save_resume_analysis,
)
from tests.conftest import RESUME_TEXT, VACANCY_TEXT, ApiUser

PASSWORD = "correct-horse-battery-staple"


async def _create_user(session) -> User:
    user = User(
        email=f"history-{uuid4().hex}@example.com",
        password_hash=hash_password(PASSWORD),
    )
    session.add(user)
    await session.commit()
    return user


async def _cleanup_user(user: User) -> None:
    async with async_session_factory() as session:
        existing = await session.get(User, user.id)
        if existing is not None:
            await session.delete(existing)
            await session.commit()


async def test_switching_active_resume_rebuilds_profile(seeded_db: None) -> None:
    """Профиль строится только по активному резюме."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            first = await save_resume_analysis(
                session,
                user.id,
                raw_text="Резюме Python",
                profile=ResumeProfile(
                    skills=(ExtractedSkill("Python", 85, confidence=0.9),)
                ),
            )
            await save_resume_analysis(
                session,
                user.id,
                raw_text="Резюме SQL",
                profile=ResumeProfile(skills=(ExtractedSkill("SQL", 60, confidence=0.8),)),
            )

            snapshot = await get_profile(session, user.id)
            keys = {topic.topic_key for topic in snapshot.topics}
            assert "sql" in keys
            assert "python" not in keys

            await activate_resume(session, user.id, first.id)

            snapshot = await get_profile(session, user.id)
            keys = {topic.topic_key for topic in snapshot.topics}
            assert "python" in keys
            assert "sql" not in keys
        finally:
            await _cleanup_user(user)


async def test_deleting_active_resume_activates_previous(seeded_db: None) -> None:
    """Удаление активного резюме переключает профиль на предыдущее."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            first = await save_resume_analysis(
                session,
                user.id,
                raw_text="Резюме Python",
                profile=ResumeProfile(
                    skills=(ExtractedSkill("Python", 85, confidence=0.9),)
                ),
            )
            second = await save_resume_analysis(
                session,
                user.id,
                raw_text="Резюме SQL",
                profile=ResumeProfile(skills=(ExtractedSkill("SQL", 60, confidence=0.8),)),
            )

            await delete_resume(session, user.id, second.id)

            remaining = (
                await session.scalars(select(Resume).where(Resume.user_id == user.id))
            ).all()
            assert [item.id for item in remaining] == [first.id]
            assert remaining[0].is_active is True
            snapshot = await get_profile(session, user.id)
            assert {topic.topic_key for topic in snapshot.topics} == {"python"}
        finally:
            await _cleanup_user(user)


async def test_clear_resumes_keeps_manual_assessments(seeded_db: None) -> None:
    """Очистка истории убирает только оценки из резюме."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            await save_resume_analysis(
                session,
                user.id,
                raw_text="Резюме Python",
                profile=ResumeProfile(
                    skills=(ExtractedSkill("Python", 85, confidence=0.9),)
                ),
            )
            docker = await session.scalar(select(Topic).where(Topic.key == "docker"))
            assert docker is not None
            session.add(
                UserSkillState(
                    user_id=user.id,
                    topic_id=docker.id,
                    proficiency=77,
                    confidence=0.9,
                    source="manual",
                )
            )
            await session.commit()
            await create_plan(session, user.id)

            await clear_resumes(session, user.id)

            resumes = (
                await session.scalars(select(Resume).where(Resume.user_id == user.id))
            ).all()
            assert resumes == []
            plans = await list_plans(session, user.id)
            assert [plan for plan in plans if plan.status == "active"] == []
            snapshot = await get_profile(session, user.id)
            topics = {topic.topic_key: topic for topic in snapshot.topics}
            assert topics["docker"].proficiency == 77
            assert topics["docker"].source == "manual"
            assert "python" not in topics
        finally:
            await _cleanup_user(user)


async def test_switching_resume_rebuilds_plan(seeded_db: None) -> None:
    """Активный план пересобирается под новое активное резюме."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            await save_resume_analysis(
                session,
                user.id,
                raw_text="Резюме Python",
                profile=ResumeProfile(
                    skills=(ExtractedSkill("Python", 85, confidence=0.9),)
                ),
            )
            first_plan = await create_plan(session, user.id)
            assert first_plan.resume_id is not None

            second = await save_resume_analysis(
                session,
                user.id,
                raw_text="Резюме SQL",
                profile=ResumeProfile(skills=(ExtractedSkill("SQL", 60, confidence=0.8),)),
            )

            plans = await list_plans(session, user.id)
            active = [plan for plan in plans if plan.status == "active"]
            assert len(active) == 1
            assert active[0].id != first_plan.id
            assert active[0].resume_id == second.id
            old_plan = await get_plan(session, user.id, first_plan.id)
            assert old_plan.status == "archived"
        finally:
            await _cleanup_user(user)


async def test_duplicate_vacancy_returns_existing(api_user: ApiUser) -> None:
    """Повторная проверка того же текста не создаёт новую вакансию."""
    first = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend", "raw_text": VACANCY_TEXT},
        headers=api_user.headers,
    )
    second = await api_user.client.post(
        "/vacancies",
        json={"title": "Backend copy", "raw_text": f"  {VACANCY_TEXT}  "},
        headers=api_user.headers,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["reused"] is True

    listed = await api_user.client.get("/vacancies", headers=api_user.headers)
    assert [item["id"] for item in listed.json()] == [first.json()["id"]]


async def test_duplicate_resume_returns_existing_and_history(api_user: ApiUser) -> None:
    """Повторное резюме не дублируется, история показывает число навыков."""
    first = await api_user.client.post(
        "/resumes",
        json={"title": "Основное", "raw_text": RESUME_TEXT},
        headers=api_user.headers,
    )
    second = await api_user.client.post(
        "/resumes",
        json={"title": "Копия", "raw_text": f"{RESUME_TEXT}\n"},
        headers=api_user.headers,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["reused"] is True
    assert second.json()["is_active"] is True

    listed = await api_user.client.get("/resumes", headers=api_user.headers)
    body = listed.json()
    assert len(body) == 1
    assert body[0]["id"] == first.json()["id"]
    assert body[0]["is_active"] is True
    assert body[0]["skills_count"] == 3


async def test_resume_activation_delete_and_clear(api_user: ApiUser) -> None:
    """Активное резюме переключается, удаляется и очищается через API."""
    first = await api_user.client.post(
        "/resumes",
        json={"title": "Первое", "raw_text": f"{RESUME_TEXT} first"},
        headers=api_user.headers,
    )
    second = await api_user.client.post(
        "/resumes",
        json={"title": "Второе", "raw_text": f"{RESUME_TEXT} second"},
        headers=api_user.headers,
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    activated = await api_user.client.post(
        f"/resumes/{first.json()['id']}/activate", headers=api_user.headers
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["is_active"] is True

    deleted = await api_user.client.delete(
        f"/resumes/{first.json()['id']}", headers=api_user.headers
    )
    assert deleted.status_code == 204, deleted.text

    listed = await api_user.client.get("/resumes", headers=api_user.headers)
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == second.json()["id"]
    assert listed.json()[0]["is_active"] is True

    cleared = await api_user.client.delete("/resumes", headers=api_user.headers)
    assert cleared.status_code == 204, cleared.text
    assert (await api_user.client.get("/resumes", headers=api_user.headers)).json() == []
    profile = await api_user.client.get("/profile", headers=api_user.headers)
    assert profile.json()["topics"] == []


async def test_resume_actions_are_owner_scoped(api_user: ApiUser, second_user: ApiUser) -> None:
    """Чужое резюме нельзя активировать или удалить."""
    created = await api_user.client.post(
        "/resumes",
        json={"title": "Своё", "raw_text": RESUME_TEXT},
        headers=api_user.headers,
    )
    resume_id = created.json()["id"]

    activated = await second_user.client.post(
        f"/resumes/{resume_id}/activate", headers=second_user.headers
    )
    deleted = await second_user.client.delete(
        f"/resumes/{resume_id}", headers=second_user.headers
    )

    assert activated.status_code == 404
    assert deleted.status_code == 404
