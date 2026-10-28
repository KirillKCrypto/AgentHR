"""Тесты инструментов агента: извлечение, чтение профиля и граф тем."""

from uuid import uuid4

import pytest

from app.agent.analysis_tools import build_analysis_tools
from app.agent.tools import ToolArgumentsError, ToolDefinition, ToolRegistry
from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models import User
from app.services.profile import NotFoundError, analyze_resume, analyze_vacancy
from tests.conftest import RESUME_TEXT, VACANCY_TEXT, SchemaStubProvider

PASSWORD = "correct-horse-battery-staple"


def _tools(session, provider: SchemaStubProvider, user_id) -> dict[str, ToolDefinition]:
    """Инструменты анализа по имени."""
    return {tool.name: tool for tool in build_analysis_tools(session, provider, user_id=user_id)}


async def _create_user(session) -> User:
    """Пользователь для тестов инструментов."""
    user = User(
        email=f"tools-{uuid4().hex}@example.com",
        password_hash=hash_password(PASSWORD),
    )
    session.add(user)
    await session.commit()
    return user


async def _cleanup_user(user: User) -> None:
    """Удаляет пользователя и его данные."""
    async with async_session_factory() as session:
        existing = await session.get(User, user.id)
        if existing is not None:
            await session.delete(existing)
            await session.commit()


def test_tool_schemas_are_registered_and_validated() -> None:
    """Инструменты описывают аргументы JSON Schema и валидируют вызовы."""
    provider = SchemaStubProvider()
    tools = build_analysis_tools(
        session=None,  # type: ignore[arg-type] — проверяются только описания
        provider=provider,
        user_id=uuid4(),
    )
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)

    assert {spec.name for spec in registry.specs()} == {
        "extract_vacancy_requirements",
        "extract_resume_skills",
        "get_vacancy_requirements",
        "get_user_skill_state",
        "query_skill_dependencies",
        "update_skill_proficiency",
        "compute_vacancy_gaps",
    }

    with pytest.raises(ToolArgumentsError):
        registry.validate_arguments("update_skill_proficiency", {"topic_key": "python"})

    with pytest.raises(ToolArgumentsError):
        registry.validate_arguments(
            "update_skill_proficiency", {"topic_key": "python", "score": 150}
        )

    registry.validate_arguments("update_skill_proficiency", {"topic_key": "python", "score": 70})


async def test_extract_vacancy_tool_returns_skills(seeded_db: None) -> None:
    """Инструмент извлечения возвращает структуру без записи в БД."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            tools = _tools(session, SchemaStubProvider(), user.id)

            result = await tools["extract_vacancy_requirements"].handler(text=VACANCY_TEXT)

            assert result["title"] == "Python-разработчик"
            assert [skill["name"] for skill in result["skills"]] == [
                "Python",
                "PostgreSQL",
                "Kafka",
            ]
            assert result["skills"][0]["required_level"] == 70
        finally:
            await _cleanup_user(user)


async def test_get_vacancy_requirements_respects_owner(seeded_db: None) -> None:
    """Инструмент не отдаёт вакансию другого пользователя."""
    provider = SchemaStubProvider()
    async with async_session_factory() as session:
        owner = await _create_user(session)
        stranger = await _create_user(session)
        try:
            vacancy = await analyze_vacancy(session, provider, owner.id, raw_text=VACANCY_TEXT)
            tools = _tools(session, provider, stranger.id)

            with pytest.raises(NotFoundError):
                await tools["get_vacancy_requirements"].handler(vacancy_id=str(vacancy.id))
        finally:
            await _cleanup_user(owner)
            await _cleanup_user(stranger)


async def test_get_user_skill_state_reads_profile(seeded_db: None) -> None:
    """Профиль в инструменте показывает темы и навыки вне онтологии."""
    provider = SchemaStubProvider()
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            await analyze_resume(session, provider, user.id, raw_text=RESUME_TEXT)
            tools = _tools(session, provider, user.id)

            result = await tools["get_user_skill_state"].handler()

            topics = {topic["topic_key"]: topic for topic in result["topics"]}
            assert topics["python"]["proficiency"] == 75
            assert topics["sql"]["proficiency"] == 50
            assert topics["docker"]["proficiency"] == 40
            assert result["unmatched_skills"] == []
        finally:
            await _cleanup_user(user)


async def test_query_skill_dependencies(seeded_db: None) -> None:
    """Инструмент графа отдаёт пререквизиты и зависимые темы."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            tools = _tools(session, SchemaStubProvider(), user.id)

            result = await tools["query_skill_dependencies"].handler(
                topic_keys=["databases", "sql", "no-such-topic"]
            )

            by_key = {item["topic_key"]: item for item in result["topics"]}
            assert by_key["databases"]["prerequisites"] == ["sql"]
            assert {"databases", "postgresql", "mysql"} <= set(by_key["sql"]["dependents"])
            assert by_key["no-such-topic"] == {
                "topic_key": "no-such-topic",
                "found": False,
            }
        finally:
            await _cleanup_user(user)


async def test_update_skill_proficiency_tool(seeded_db: None) -> None:
    """Инструмент обновляет профиль и возвращает новое состояние."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            tools = _tools(session, SchemaStubProvider(), user.id)

            result = await tools["update_skill_proficiency"].handler(
                topic_key="python", score=80, evidence="подтвердил на созвоне"
            )

            assert result == {
                "topic_key": "python",
                "proficiency": 80,
                "confidence": 0.95,
                "source": "manual",
            }
        finally:
            await _cleanup_user(user)


async def test_invalid_vacancy_uuid_is_rejected(seeded_db: None) -> None:
    """Невалидный UUID — понятная ошибка инструмента."""
    async with async_session_factory() as session:
        user = await _create_user(session)
        try:
            tools = _tools(session, SchemaStubProvider(), user.id)

            with pytest.raises(ValueError, match="UUID"):
                await tools["get_vacancy_requirements"].handler(vacancy_id="not-a-uuid")
        finally:
            await _cleanup_user(user)
