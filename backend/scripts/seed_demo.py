"""Демо-данные AgentHR: пользователь, профиль, вакансия и план.

Запуск из backend:
    uv run python -m scripts.seed_demo
"""

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models import (
    Resume,
    ResumeSkill,
    Topic,
    User,
    UserSkillState,
    Vacancy,
    VacancySkill,
)
from app.ontology.seed import seed_ontology
from app.services.plans import create_plan

EMAIL = "demo@agenthr.dev"
LEGACY_EMAIL = "demo@agenthr.local"
PASSWORD = "Demo12345"

PROFILE = {
    "python": (82, 0.9),
    "sql": (45, 0.5),
    "docker": (35, 0.4),
    "fastapi": (55, 0.6),
    "redis": (30, 0.4),
    "kafka": (20, 0.3),
}

REQUIREMENTS = {
    "python": (80, 1.0, "must_have"),
    "sql": (75, 0.9, "must_have"),
    "docker": (70, 0.6, "must_have"),
    "fastapi": (70, 0.5, "nice_to_have"),
    "redis": (60, 0.4, "nice_to_have"),
    "kafka": (60, 0.3, "nice_to_have"),
}


async def main() -> None:
    """Создаёт демо-пользователя и данные, если их ещё нет."""
    async with async_session_factory() as session:
        await seed_ontology(session)
        user = await session.scalar(select(User).where(User.email == EMAIL))
        if user is None:
            legacy = await session.scalar(
                select(User).where(User.email == LEGACY_EMAIL)
            )
            if legacy is not None:
                legacy.email = EMAIL
                user = legacy
            else:
                user = User(email=EMAIL, password_hash=hash_password(PASSWORD))
                session.add(user)
                await session.flush()

        topics = {
            topic.key: topic
            for topic in (
                await session.scalars(
                    select(Topic).where(Topic.key.in_(set(PROFILE) | set(REQUIREMENTS)))
                )
            ).all()
        }

        resume = await session.scalar(
            select(Resume).where(Resume.user_id == user.id).limit(1)
        )
        created_resume = resume is None
        if resume is None:
            resume = Resume(
                user_id=user.id,
                title="Демо-резюме backend-разработчика",
                raw_text="Python, SQL, Docker, FastAPI, Redis, Kafka",
            )
            session.add(resume)
            await session.flush()

        for key, (level, confidence) in PROFILE.items():
            topic = topics.get(key)
            if topic is None:
                continue
            if created_resume:
                session.add(
                    ResumeSkill(
                        resume_id=resume.id,
                        topic_id=topic.id,
                        raw_name=topic.name,
                        proficiency=level,
                        confidence=confidence,
                        evidence="Демо-навык",
                        match_method="manual",
                    )
                )
            state = await session.scalar(
                select(UserSkillState).where(
                    UserSkillState.user_id == user.id,
                    UserSkillState.topic_id == topic.id,
                )
            )
            if state is None:
                state = UserSkillState(user_id=user.id, topic_id=topic.id)
                session.add(state)
            state.proficiency = level
            state.confidence = confidence
            state.source = "resume"

        vacancy = await session.scalar(
            select(Vacancy).where(Vacancy.user_id == user.id).limit(1)
        )
        if vacancy is None:
            vacancy = Vacancy(
                user_id=user.id,
                title="Senior Python Developer",
                company="Demo Company",
                level="senior",
                raw_text="Python, SQL, Docker, FastAPI, Redis, Kafka",
            )
            session.add(vacancy)
            await session.flush()
            for key, (level, weight, criticality) in REQUIREMENTS.items():
                topic = topics.get(key)
                if topic is None:
                    continue
                session.add(
                    VacancySkill(
                        vacancy_id=vacancy.id,
                        topic_id=topic.id,
                        raw_name=topic.name,
                        required_level=level,
                        weight=weight,
                        criticality=criticality,
                        confidence=0.9,
                        evidence="Демо-требование",
                        match_method="manual",
                    )
                )

        await session.commit()

    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == EMAIL))
        vacancy = await session.scalar(
            select(Vacancy).where(Vacancy.user_id == user.id).limit(1)
        )
        plan = await create_plan(session, user.id, vacancy_id=vacancy.id)

    print(f"Демо-пользователь: {EMAIL}")
    print(f"Пароль: {PASSWORD}")
    print(f"План: {plan.id} ({len(plan.items)} тем)")


if __name__ == "__main__":
    asyncio.run(main())
