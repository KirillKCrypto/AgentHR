"""Ревью provisional-тем: approve, reject и merge."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models import (
    OntologyReviewAction,
    Resume,
    ResumeSkill,
    Topic,
    TopicAlias,
    TopicCandidate,
    TopicPrerequisite,
    User,
    UserSkillState,
    Vacancy,
    VacancySkill,
)
from app.services.normalization import normalize_name
from app.services.ontology_review import (
    ReviewError,
    approve_topic,
    list_review_topics,
    merge_topics,
    reject_topic,
)


def _key(prefix: str) -> str:
    """Уникальный ключ тестовой темы."""
    return f"review-test-{prefix}-{uuid4().hex[:8]}"


async def _make_topic(
    session,
    *,
    name: str,
    status: str = "provisional",
    key_prefix: str = "topic",
) -> Topic:
    """Создаёт тему нужного статуса."""
    topic = Topic(
        key=_key(key_prefix),
        name=name,
        description=f"Тестовая тема {name}",
        category="auto" if status == "provisional" else "test",
        aliases=[],
        status=status,
        origin="auto" if status == "provisional" else "manual",
        is_auto_generated=status == "provisional",
    )
    session.add(topic)
    await session.flush()
    return topic


async def _cleanup(keys: list[str], email: str | None = None) -> None:
    """Удаляет данные теста, не оставляя provisional-мусора."""
    async with async_session_factory() as session:
        if email is not None:
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                await session.delete(user)
        topics = (await session.scalars(select(Topic).where(Topic.key.in_(keys)))).all()
        topic_ids = [topic.id for topic in topics]
        if topic_ids:
            await session.execute(delete(ResumeSkill).where(ResumeSkill.topic_id.in_(topic_ids)))
            await session.execute(delete(VacancySkill).where(VacancySkill.topic_id.in_(topic_ids)))
            await session.execute(
                delete(UserSkillState).where(UserSkillState.topic_id.in_(topic_ids))
            )
            await session.execute(
                delete(OntologyReviewAction).where(
                    OntologyReviewAction.source_topic_id.in_(topic_ids)
                    | OntologyReviewAction.target_topic_id.in_(topic_ids)
                )
            )
            await session.execute(
                delete(TopicCandidate).where(TopicCandidate.topic_id.in_(topic_ids))
            )
            await session.execute(delete(Topic).where(Topic.id.in_(topic_ids)))
        await session.commit()


async def test_approve_provisional_topic(seeded_db: None) -> None:
    """Approve переводит provisional в canonical и фиксирует аудит."""
    key = _key("approve")
    try:
        async with async_session_factory() as session:
            topic = await _make_topic(session, name="Review approve", key_prefix="approve")
            key = topic.key
            session.add(
                TopicCandidate(
                    name="Review approve",
                    normalized_name=normalize_name("Review approve"),
                    topic_id=topic.id,
                    status="auto_created",
                    sources=[],
                )
            )
            await session.flush()

            listed = await list_review_topics(session)
            assert any(item.key == key for item in listed)

            await approve_topic(session, key, actor="tester")
            await session.commit()

        async with async_session_factory() as session:
            topic = await session.scalar(select(Topic).where(Topic.key == key))
            candidate = await session.scalar(
                select(TopicCandidate).where(TopicCandidate.topic_id == topic.id)
            )
            action = await session.scalar(
                select(OntologyReviewAction).where(
                    OntologyReviewAction.source_topic_id == topic.id,
                    OntologyReviewAction.action == "approve",
                )
            )
        assert topic.status == "canonical"
        assert candidate.status == "approved"
        assert action is not None
        assert action.actor == "tester"
    finally:
        await _cleanup([key])


async def test_reject_requires_empty_topic(seeded_db: None) -> None:
    """Пустую provisional-тему можно отклонить, тему со ссылками — нельзя."""
    email = f"review-{uuid4().hex}@example.com"
    empty_key = _key("reject-empty")
    used_key = _key("reject-used")
    try:
        async with async_session_factory() as session:
            empty = await _make_topic(session, name="Empty", key_prefix="reject-empty")
            empty_key = empty.key
            used = await _make_topic(session, name="Used", key_prefix="reject-used")
            used_key = used.key
            user = User(email=email, password_hash="test")
            session.add(user)
            await session.flush()
            resume = Resume(user_id=user.id, title=None, raw_text="test")
            session.add(resume)
            await session.flush()
            session.add(
                ResumeSkill(
                    resume_id=resume.id,
                    topic_id=used.id,
                    raw_name="Used",
                    proficiency=40,
                    confidence=0.5,
                    match_method="provisional",
                )
            )
            await session.commit()

            await reject_topic(session, empty_key, actor="tester")
            with pytest.raises(ReviewError, match="нельзя отклонить"):
                await reject_topic(session, used_key, actor="tester")
            await session.commit()

        async with async_session_factory() as session:
            empty = await session.scalar(select(Topic).where(Topic.key == empty_key))
            used = await session.scalar(select(Topic).where(Topic.key == used_key))
        assert empty.status == "rejected"
        assert used.status == "provisional"
    finally:
        await _cleanup([empty_key, used_key], email=email)


async def test_merge_moves_skills_states_aliases_and_edges(seeded_db: None) -> None:
    """Merge переносит все связи source на target и помечает source merged."""
    email = f"review-{uuid4().hex}@example.com"
    keys: list[str] = []
    try:
        async with async_session_factory() as session:
            source = await _make_topic(session, name="Source topic", key_prefix="merge-source")
            target = await _make_topic(
                session, name="Target topic", status="canonical", key_prefix="merge-target"
            )
            other = await _make_topic(
                session, name="Other topic", status="canonical", key_prefix="merge-other"
            )
            source_key = source.key
            target_key = target.key
            other_key = other.key
            keys = [source_key, target_key, other_key]
            python = await session.scalar(select(Topic).where(Topic.key == "python"))
            assert python is not None
            python_id = python.id

            user = User(email=email, password_hash="test")
            session.add(user)
            await session.flush()
            resume = Resume(user_id=user.id, title=None, raw_text="test")
            vacancy = Vacancy(user_id=user.id, title=None, raw_text="test")
            session.add_all([resume, vacancy])
            await session.flush()
            session.add_all(
                [
                    ResumeSkill(
                        resume_id=resume.id,
                        topic_id=source.id,
                        raw_name="Source skill",
                        proficiency=50,
                        confidence=0.5,
                        match_method="provisional",
                    ),
                    VacancySkill(
                        vacancy_id=vacancy.id,
                        topic_id=source.id,
                        raw_name="Source skill",
                        required_level=60,
                        weight=1.0,
                        confidence=0.5,
                        match_method="provisional",
                    ),
                    UserSkillState(
                        user_id=user.id,
                        topic_id=source.id,
                        proficiency=50,
                        confidence=0.5,
                        source="resume",
                        evidence=[{"type": "resume", "text": "source"}],
                        last_assessed=datetime(2026, 1, 1, tzinfo=UTC),
                    ),
                    UserSkillState(
                        user_id=user.id,
                        topic_id=target.id,
                        proficiency=70,
                        confidence=0.5,
                        source="resume",
                        evidence=[{"type": "resume", "text": "target"}],
                        last_assessed=datetime(2026, 2, 1, tzinfo=UTC),
                    ),
                    TopicAlias(
                        topic_id=source.id,
                        alias="source alias",
                        normalized_alias=normalize_name("source alias"),
                        source="auto",
                    ),
                    TopicCandidate(
                        name="Source topic",
                        normalized_name=normalize_name("Source topic"),
                        topic_id=source.id,
                        status="auto_created",
                        sources=[],
                    ),
                    # source требует python; target тоже требует python — дубль должен схлопнуться
                    TopicPrerequisite(topic_id=source.id, prerequisite_id=python_id),
                    TopicPrerequisite(topic_id=target.id, prerequisite_id=python_id),
                    # other требует source; после merge должен требовать target
                    TopicPrerequisite(topic_id=other.id, prerequisite_id=source.id),
                ]
            )
            await session.commit()

            await merge_topics(session, source_key, target_key, actor="tester")
            await session.commit()

        async with async_session_factory() as session:
            source = await session.scalar(select(Topic).where(Topic.key == source_key))
            target = await session.scalar(select(Topic).where(Topic.key == target_key))
            other = await session.scalar(select(Topic).where(Topic.key == other_key))
            resume_skill = await session.scalar(
                select(ResumeSkill).where(ResumeSkill.raw_name == "Source skill")
            )
            vacancy_skill = await session.scalar(
                select(VacancySkill).where(VacancySkill.raw_name == "Source skill")
            )
            source_state = await session.scalar(
                select(UserSkillState).where(UserSkillState.topic_id == source.id)
            )
            target_state = await session.scalar(
                select(UserSkillState).where(UserSkillState.topic_id == target.id)
            )
            alias = await session.scalar(
                select(TopicAlias).where(
                    TopicAlias.normalized_alias == normalize_name("source alias")
                )
            )
            candidate = await session.scalar(
                select(TopicCandidate).where(
                    TopicCandidate.normalized_name == normalize_name("Source topic")
                )
            )
            target_python = await session.scalar(
                select(TopicPrerequisite).where(
                    TopicPrerequisite.topic_id == target.id,
                    TopicPrerequisite.prerequisite_id == python_id,
                )
            )
            other_target = await session.scalar(
                select(TopicPrerequisite).where(
                    TopicPrerequisite.topic_id == other.id,
                    TopicPrerequisite.prerequisite_id == target.id,
                )
            )
            action = await session.scalar(
                select(OntologyReviewAction).where(
                    OntologyReviewAction.action == "merge",
                    OntologyReviewAction.source_topic_id == source.id,
                )
            )

        assert source.status == "merged"
        assert source.canonical_topic_id == target.id
        assert resume_skill.topic_id == target.id
        assert vacancy_skill.topic_id == target.id
        assert source_state is None
        assert target_state.proficiency == 60
        assert len(target_state.evidence) == 2
        assert alias.topic_id == target.id
        assert candidate.topic_id == target.id
        assert candidate.status == "merged"
        assert target_python is not None
        assert other_target is not None
        assert action is not None
        assert action.details["skills_moved"] == 2
    finally:
        await _cleanup(keys, email=email)
