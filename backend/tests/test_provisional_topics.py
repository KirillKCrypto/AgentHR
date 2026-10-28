"""Новые навыки не остаются вне онтологии: создаётся provisional-тема."""

from uuid import uuid4

from sqlalchemy import delete, func, select

from app.db.session import async_session_factory
from app.models import ResumeSkill, Topic, TopicAlias, TopicCandidate, VacancySkill
from app.services.normalization import TopicMatch, normalize_name
from app.services.topics import resolve_or_create_topics
from tests.conftest import ApiUser


def _unknown_skill() -> str:
    """Уникальное имя, которого заведомо нет в словаре."""
    return f"Quantum YAML Orchestrator {uuid4().hex[:8]}"


async def _cleanup_topic(name: str) -> None:
    """Удаляет provisional-тему и кандидата, созданных тестом."""
    async with async_session_factory() as session:
        normalized = normalize_name(name)
        candidate = await session.scalar(
            select(TopicCandidate).where(TopicCandidate.normalized_name == normalized)
        )
        topic_id = candidate.topic_id if candidate is not None else None
        if candidate is not None:
            await session.delete(candidate)
        if topic_id is not None:
            await session.execute(delete(ResumeSkill).where(ResumeSkill.topic_id == topic_id))
            await session.execute(delete(VacancySkill).where(VacancySkill.topic_id == topic_id))
            topic = await session.get(Topic, topic_id)
            if topic is not None:
                await session.delete(topic)
        await session.commit()


async def test_unknown_resume_skill_creates_provisional_topic(api_user: ApiUser) -> None:
    """Резюме с новым навыком получает provisional-тему и не попадает в unmatched."""
    name = _unknown_skill()
    api_user.provider.responses["resume_skills"] = {
        "experience_years": 1.0,
        "self_level": "junior",
        "skills": [
            {
                "name": name,
                "proficiency": 45,
                "evidence": "использовал на учебном проекте",
                "confidence": 0.7,
            }
        ],
    }

    try:
        first = await api_user.client.post(
            "/resumes",
            json={"title": "Резюме", "raw_text": "Резюме с новым навыком"},
            headers=api_user.headers,
        )
        assert first.status_code == 201, first.text
        first_skill = first.json()["skills"][0]
        assert first_skill["match_method"] == "provisional"
        assert first_skill["topic"] is not None
        topic_key = first_skill["topic"]["key"]
        assert topic_key.startswith("auto-")

        async with async_session_factory() as session:
            resume_skill = await session.scalar(
                select(ResumeSkill).where(ResumeSkill.raw_name == name)
            )
            assert resume_skill is not None
            assert resume_skill.topic_id is not None

            topic = await session.get(Topic, resume_skill.topic_id)
            assert topic is not None
            assert topic.status == "provisional"
            assert topic.origin == "auto"
            assert topic.is_auto_generated is True

            candidate = await session.scalar(
                select(TopicCandidate).where(TopicCandidate.normalized_name == normalize_name(name))
            )
            assert candidate is not None
            assert candidate.status == "auto_created"
            assert candidate.topic_id == topic.id

        profile = await api_user.client.get("/profile", headers=api_user.headers)
        assert profile.status_code == 200
        assert profile.json()["unmatched_skills"] == []
        profile_topics = {
            topic["topic_key"]: topic for topic in profile.json()["topics"]
        }
        assert profile_topics[topic_key]["status"] == "provisional"

        # Повторное упоминание переиспользует ту же provisional-тему.
        second = await api_user.client.post(
            "/resumes",
            json={"title": "Резюме 2", "raw_text": "Тот же новый навык"},
            headers=api_user.headers,
        )
        assert second.status_code == 201, second.text
        assert second.json()["skills"][0]["topic"]["key"] == topic_key

        async with async_session_factory() as session:
            count = await session.scalar(select(Topic.id).where(Topic.key == topic_key))
            alias = await session.scalar(
                select(TopicAlias).where(TopicAlias.normalized_alias == normalize_name(name))
            )
        assert count is not None
        assert alias is not None
    finally:
        await _cleanup_topic(name)


async def test_auto_topic_limit_groups_overflow(seeded_db: None) -> None:
    """При исчерпании лимита новые навыки идут в одну review-тему."""
    first = _unknown_skill()
    second = _unknown_skill()
    source_id = uuid4()
    topic_id = None

    try:
        async with async_session_factory() as session:
            resolved = await resolve_or_create_topics(
                session,
                [(first, None), (second, None)],
                [
                    TopicMatch(None, "none", 0.0),
                    TopicMatch(None, "none", 0.0),
                ],
                source_type="vacancy",
                source_id=source_id,
                auto_topic_limit=0,
            )
            await session.commit()
            topic_id = resolved[0].topic_id
            assert topic_id is not None
            assert resolved[1].topic_id == topic_id

            topic = await session.get(Topic, topic_id)
            assert topic is not None
            assert topic.key.startswith("auto-review-")
            assert topic.status == "provisional"

            candidate_count = await session.scalar(
                select(func.count())
                .select_from(TopicCandidate)
                .where(TopicCandidate.topic_id == topic_id)
            )
            assert candidate_count == 2
    finally:
        if topic_id is not None:
            async with async_session_factory() as session:
                await session.execute(
                    delete(TopicCandidate).where(TopicCandidate.topic_id == topic_id)
                )
                await session.execute(delete(Topic).where(Topic.id == topic_id))
                await session.commit()


async def test_unknown_vacancy_skill_gets_topic_and_gap(api_user: ApiUser) -> None:
    """Требование вакансии с новым навыком тоже получает topic_id."""
    name = _unknown_skill()
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Экспериментальная вакансия",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": name,
                "required_level": 60,
                "weight": 1.0,
                "evidence": "нестандартный стек",
                "confidence": 0.8,
            },
            {
                "name": "Python",
                "required_level": 60,
                "weight": 1.0,
                "evidence": "основной язык",
                "confidence": 0.9,
            },
        ],
    }
    api_user.provider.responses["resume_skills"] = {
        "experience_years": 2.0,
        "self_level": "middle",
        "skills": [
            {
                "name": "Python",
                "proficiency": 80,
                "evidence": "два года",
                "confidence": 0.9,
            }
        ],
    }

    try:
        response = await api_user.client.post(
            "/vacancies",
            json={"title": "Экспериментальная вакансия", "raw_text": "Новый стек"},
            headers=api_user.headers,
        )
        assert response.status_code == 201, response.text
        vacancy = response.json()
        skill = next(item for item in vacancy["skills"] if item["raw_name"] == name)
        assert skill["match_method"] == "provisional"
        assert skill["topic"] is not None

        resume_response = await api_user.client.post(
            "/resumes",
            json={"title": "Резюме", "raw_text": "Python"},
            headers=api_user.headers,
        )
        assert resume_response.status_code == 201, resume_response.text
        analysis = await api_user.client.post(
            "/analysis",
            json={
                "vacancy_id": vacancy["id"],
                "resume_id": resume_response.json()["id"],
            },
            headers=api_user.headers,
        )
        assert analysis.status_code == 200, analysis.text
        gaps = analysis.json()["gaps"]
        assert gaps["provisional_count"] == 1
        assert gaps["provisional_weight"] == 1.0
        assert gaps["confirmed_weight"] == 1.0
        assert gaps["confirmed_readiness"] == 1.0
        assert gaps["coverage_all"] == 0.5
        provisional_item = next(item for item in gaps["items"] if item["skill_name"] == name)
        assert provisional_item["topic_status"] == "provisional"

        async with async_session_factory() as session:
            vacancy_skill = await session.scalar(
                select(VacancySkill).where(VacancySkill.raw_name == name)
            )
            assert vacancy_skill is not None
            assert vacancy_skill.topic_id is not None
    finally:
        await _cleanup_topic(name)
