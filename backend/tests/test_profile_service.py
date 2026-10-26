"""Тесты сервисного слоя профиля: взвешивание оценок и источники истины."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models import Resume, ResumeSkill, Topic, User, UserSkillState
from app.services.profile import (
    NotFoundError,
    get_profile,
    rebuild_profile,
    update_skill_proficiency,
    weighted_estimate,
)

PASSWORD = "correct-horse-battery-staple"


def test_weighted_estimate_averages_by_confidence() -> None:
    """Уровень — среднее по уверенности, уверенность агрегата растёт."""
    level, confidence = weighted_estimate([(60, 0.5), (80, 1.0)])

    assert level == round((60 * 0.5 + 80 * 1.0) / 1.5)
    # Уверенность ограничена потолком: полного доверия к оценке не бывает
    assert confidence == pytest.approx(0.95)


def test_weighted_estimate_ignores_zero_confidence() -> None:
    """Свидетельства без уверенности не влияют на оценку."""
    assert weighted_estimate([]) == (0, 0.0)
    assert weighted_estimate([(90, 0.0)]) == (0, 0.0)


def test_weighted_estimate_caps_confidence() -> None:
    """Много согласованных свидетельств не дают 100% уверенности."""
    _, confidence = weighted_estimate([(70, 0.9)] * 5)

    assert confidence == pytest.approx(0.95)


async def _create_user(session) -> User:
    """Создаёт пользователя для сервисных тестов."""
    user = User(
        email=f"service-{uuid4().hex}@example.com",
        password_hash=hash_password(PASSWORD),
    )
    session.add(user)
    await session.commit()
    return user


async def _cleanup_user(user: User) -> None:
    """Удаляет пользователя вместе с документами (каскад в БД)."""
    async with async_session_factory() as session:
        existing = await session.get(User, user.id)
        if existing is not None:
            await session.delete(existing)
            await session.commit()


async def test_rebuild_profile_keeps_interview_estimate(seeded_db: None) -> None:
    """Пересчёт по резюме не занижает оценку, полученную на собеседовании."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            topic = await session.scalar(select(Topic).where(Topic.key == "python"))
            assert topic is not None

            session.add(
                UserSkillState(
                    user_id=user.id,
                    topic_id=topic.id,
                    proficiency=90,
                    confidence=0.9,
                    source="interview",
                )
            )
            resume = Resume(user_id=user.id, raw_text="Python, базовый уровень")
            session.add(resume)
            await session.flush()
            session.add(
                ResumeSkill(
                    resume_id=resume.id,
                    topic_id=topic.id,
                    raw_name="Python",
                    proficiency=30,
                    confidence=0.6,
                    match_method="exact",
                )
            )
            await session.commit()

            snapshot = await rebuild_profile(session, user.id)

            python = next(item for item in snapshot.topics if item.topic_key == "python")
            assert python.proficiency == 90
            assert python.source == "interview"
        finally:
            await _cleanup_user(user)


async def test_update_skill_proficiency_merges_with_resume(seeded_db: None) -> None:
    """Ручная оценка объединяется с резюме и повышает уверенность."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            topic = await session.scalar(select(Topic).where(Topic.key == "python"))
            assert topic is not None
            session.add(
                UserSkillState(
                    user_id=user.id,
                    topic_id=topic.id,
                    proficiency=50,
                    confidence=0.6,
                    source="resume",
                )
            )
            await session.commit()

            updated = await update_skill_proficiency(
                session,
                user.id,
                topic_key="python",
                score=80,
                evidence="подтвердил на созвоне",
                source="manual",
            )

            # Вес резюме: 0.6 * 0.6 = 0.36; вес ручной оценки: 1.0
            assert updated.proficiency == round((50 * 0.36 + 80 * 1.0) / 1.36)
            assert updated.confidence == pytest.approx(0.95)
            assert updated.source == "manual"

            snapshot = await get_profile(session, user.id)
            python = next(item for item in snapshot.topics if item.topic_key == "python")
            assert python.proficiency == updated.proficiency
        finally:
            await _cleanup_user(user)


async def test_update_unknown_topic_raises(seeded_db: None) -> None:
    """Неизвестная тема — понятная ошибка, а не молчаливая запись."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            with pytest.raises(NotFoundError):
                await update_skill_proficiency(
                    session, user.id, topic_key="no-such-topic", score=50
                )
        finally:
            await _cleanup_user(user)
