"""Интеграционный тест сида онтологии (требуется запущенная БД из infra/)."""

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import async_session_factory, engine
from app.models import ResumeSkill, Topic, TopicAlias, TopicPrerequisite, VacancySkill
from app.ontology import ONTOLOGY_TOPICS, ONTOLOGY_VERSION
from app.ontology.seed import seed_ontology
from app.services.topics import create_skill_matcher, load_topic_index

AUTO_TOPIC_KEY = "test-auto-generated-topic"


async def _database_available() -> bool:
    """Проверяет доступность БД, чтобы пропустить тест без запущенного Postgres."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True


def _desired_edge_count() -> int:
    """Сколько рёбер REQUIRES должно быть в онтологии."""
    return sum(len(topic.prerequisites) for topic in ONTOLOGY_TOPICS)


async def test_seed_creates_topics_and_edges() -> None:
    """Сид создаёт все темы онтологии и связи между ними."""
    if not await _database_available():
        pytest.skip("PostgreSQL недоступен — интеграционный тест пропущен")

    try:
        async with async_session_factory() as session:
            await seed_ontology(session)

        async with async_session_factory() as session:
            topics = (
                await session.scalars(
                    select(Topic).where(Topic.key.in_([topic.key for topic in ONTOLOGY_TOPICS]))
                )
            ).all()
            edges = (await session.scalars(select(TopicPrerequisite))).all()
            aliases = (
                await session.scalars(
                    select(TopicAlias).where(
                        TopicAlias.topic_id.in_([topic.id for topic in topics])
                    )
                )
            ).all()

        assert len(topics) == len(ONTOLOGY_TOPICS)
        assert len(edges) == _desired_edge_count()
        assert len(aliases) >= len(ONTOLOGY_TOPICS)
        assert all(topic.ontology_version == ONTOLOGY_VERSION for topic in topics)
        assert all(topic.status == "canonical" for topic in topics)
        assert all(topic.origin == "seed" for topic in topics)
        assert all(topic.aliases for topic in topics)
        assert all(topic.description for topic in topics)
    finally:
        await engine.dispose()


async def test_seed_is_idempotent() -> None:
    """Повторный сид не создаёт ни тем, ни связей заново."""
    if not await _database_available():
        pytest.skip("PostgreSQL недоступен — интеграционный тест пропущен")

    try:
        async with async_session_factory() as session:
            first = await seed_ontology(session)
        async with async_session_factory() as session:
            second = await seed_ontology(session)
            seeded_keys = [topic.key for topic in ONTOLOGY_TOPICS]
            topic_count = await session.scalar(
                select(func.count()).select_from(Topic).where(Topic.key.in_(seeded_keys))
            )
            edge_count = await session.scalar(select(func.count()).select_from(TopicPrerequisite))

        assert first.topics_created == 0
        assert second.topics_created == 0
        assert second.topics_updated == 0
        assert second.edges_created == 0
        assert second.edges_removed == 0
        assert topic_count == len(ONTOLOGY_TOPICS)
        assert edge_count == _desired_edge_count()
    finally:
        await engine.dispose()


async def test_seed_aliases_are_searchable(seeded_db: None) -> None:
    """Алиасы из таблицы участвуют в нормализации навыков."""
    async with async_session_factory() as session:
        index = await load_topic_index(session)
        matcher = create_skill_matcher(index)
        match = await matcher.match("postgres")

    assert match.topic_key == "postgresql"
    assert match.method == "alias"


async def test_skill_topic_id_is_required(seeded_db: None) -> None:
    """После backfill у навыков не остаётся NULL topic_id."""
    async with async_session_factory() as session:
        nullable = (
            await session.execute(
                text(
                    """
                    SELECT table_name, is_nullable
                    FROM information_schema.columns
                    WHERE table_name IN ('resume_skills', 'vacancy_skills')
                      AND column_name = 'topic_id'
                    """
                )
            )
        ).all()
        resume_nulls = await session.scalar(
            select(func.count()).select_from(ResumeSkill).where(ResumeSkill.topic_id.is_(None))
        )
        vacancy_nulls = await session.scalar(
            select(func.count()).select_from(VacancySkill).where(VacancySkill.topic_id.is_(None))
        )

    assert len(nullable) == 2
    assert all(row.is_nullable == "NO" for row in nullable)
    assert resume_nulls == 0
    assert vacancy_nulls == 0


async def test_seed_restores_changed_description() -> None:
    """Сид возвращает описание темы к состоянию пакета онтологии."""
    if not await _database_available():
        pytest.skip("PostgreSQL недоступен — интеграционный тест пропущен")

    try:
        async with async_session_factory() as session:
            topic = await session.scalar(select(Topic).where(Topic.key == "python"))
            assert topic is not None
            topic.description = "испорченное описание"
            await session.commit()

            result = await seed_ontology(session)

        assert result.topics_updated == 1
        async with async_session_factory() as session:
            restored = await session.scalar(select(Topic).where(Topic.key == "python"))
        assert restored is not None
        assert restored.description != "испорченное описание"
        assert restored.description.strip()
    finally:
        await engine.dispose()


async def test_seed_keeps_auto_generated_topics() -> None:
    """Сид не удаляет темы, созданные автоматически из кандидатов."""
    if not await _database_available():
        pytest.skip("PostgreSQL недоступен — интеграционный тест пропущен")

    try:
        async with async_session_factory() as session:
            session.add(
                Topic(
                    key=AUTO_TOPIC_KEY,
                    name="Авто-тема",
                    description="Тема, созданная автоматически из кандидата",
                    category="auto",
                    aliases=["авто"],
                    is_auto_generated=True,
                )
            )
            await session.commit()

            await seed_ontology(session)

        async with async_session_factory() as session:
            auto_topic = await session.scalar(select(Topic).where(Topic.key == AUTO_TOPIC_KEY))
        assert auto_topic is not None
        assert auto_topic.is_auto_generated is True
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Topic).where(Topic.key == AUTO_TOPIC_KEY))
            await session.commit()
        await engine.dispose()
