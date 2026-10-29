"""Инструменты агента для анализа документов и работы с профилем знаний.

Все инструменты привязаны к пользователю и сессии БД в момент сборки реестра:
`user_id` не приходит от модели, поэтому агент физически не может прочитать
или изменить чужие данные (изоляция по `user_id` на уровне tools).
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import ToolDefinition, ToolRegistry
from app.embeddings.base import EmbeddingProvider
from app.llm.base import LLMProvider
from app.models import Topic, TopicPrerequisite
from app.services.analysis import extract_resume_skills, extract_vacancy_requirements
from app.services.profile import (
    SkillEntry,
    compute_gaps,
    get_profile,
    get_vacancy,
    load_vacancy_skills,
    update_skill_proficiency,
)

_TOPIC_KEYS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topic_keys": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ключи тем онтологии, например ['sql', 'databases']",
        }
    },
    "required": ["topic_keys"],
    "additionalProperties": False,
}


def build_analysis_tools(
    session: AsyncSession,
    provider: LLMProvider,
    *,
    user_id: uuid.UUID,
    embedder: EmbeddingProvider | None = None,
) -> list[ToolDefinition]:
    """Собирает инструменты анализа, привязанные к пользователю и сессии."""

    async def extract_vacancy(text: str) -> dict[str, Any]:
        """Извлекает требования вакансии из текста (без записи в БД)."""
        result = await extract_vacancy_requirements(provider, text)
        return {
            "title": result.title,
            "company": result.company,
            "level": result.level,
            "skills": [
                {
                    "name": skill.name,
                    "required_level": skill.level,
                    "weight": skill.weight,
                    "evidence": skill.evidence,
                    "confidence": skill.confidence,
                }
                for skill in result.skills
            ],
        }

    async def extract_resume(text: str) -> dict[str, Any]:
        """Извлекает навыки и опыт из текста резюме (без записи в БД)."""
        result = await extract_resume_skills(provider, text)
        return {
            "experience_years": result.experience_years,
            "self_level": result.self_level,
            "skills": [
                {
                    "name": skill.name,
                    "proficiency": skill.level,
                    "evidence": skill.evidence,
                    "confidence": skill.confidence,
                }
                for skill in result.skills
            ],
        }

    async def vacancy_requirements(vacancy_id: str) -> dict[str, Any]:
        """Возвращает требования сохранённой вакансии пользователя."""
        vacancy = await get_vacancy(session, user_id, _as_uuid(vacancy_id, "vacancy_id"))
        skills = await load_vacancy_skills(session, vacancy.id)
        return {
            "vacancy_id": str(vacancy.id),
            "title": vacancy.title,
            "company": vacancy.company,
            "skills": [_skill_payload(skill) for skill in skills],
        }

    async def user_skill_state() -> dict[str, Any]:
        """Возвращает профиль знаний текущего пользователя."""
        snapshot = await get_profile(session, user_id)
        return {
            "user_id": str(snapshot.user_id),
            "topics": [
                {
                    "topic_key": topic.topic_key,
                    "topic_name": topic.topic_name,
                    "proficiency": topic.proficiency,
                    "confidence": topic.confidence,
                    "source": topic.source,
                    "status": topic.status,
                    "last_assessed": (
                        topic.last_assessed.isoformat() if topic.last_assessed else None
                    ),
                }
                for topic in snapshot.topics
            ],
            "unmatched_skills": [
                {
                    "name": skill.raw_name,
                    "level": skill.level,
                    "confidence": skill.confidence,
                }
                for skill in snapshot.unmatched_skills
            ],
        }

    async def skill_dependencies(topic_keys: list[str]) -> dict[str, Any]:
        """Возвращает пререквизиты и зависимые темы для указанных тем."""
        topics = {topic.key: topic for topic in (await session.scalars(select(Topic))).all()}
        by_id = {topic.id: topic.key for topic in topics.values()}
        edges = (await session.scalars(select(TopicPrerequisite))).all()

        prerequisites: dict[str, list[str]] = {}
        dependents: dict[str, list[str]] = {}
        for edge in edges:
            topic_key = by_id.get(edge.topic_id)
            prerequisite_key = by_id.get(edge.prerequisite_id)
            if topic_key is None or prerequisite_key is None:
                continue
            prerequisites.setdefault(topic_key, []).append(prerequisite_key)
            dependents.setdefault(prerequisite_key, []).append(topic_key)

        result: list[dict[str, Any]] = []
        for key in topic_keys:
            topic = topics.get(key)
            if topic is None:
                result.append({"topic_key": key, "found": False})
                continue
            result.append(
                {
                    "topic_key": topic.key,
                    "topic_name": topic.name,
                    "found": True,
                    "prerequisites": sorted(prerequisites.get(topic.key, [])),
                    "dependents": sorted(dependents.get(topic.key, [])),
                }
            )
        return {"topics": result}

    async def update_proficiency(
        topic_key: str, score: int, evidence: str | None = None
    ) -> dict[str, Any]:
        """Обновляет оценку владения темой в профиле пользователя."""
        topic = await update_skill_proficiency(
            session,
            user_id,
            topic_key=topic_key,
            score=score,
            evidence=evidence,
            source="manual",
        )
        return {
            "topic_key": topic.topic_key,
            "proficiency": topic.proficiency,
            "confidence": topic.confidence,
            "source": topic.source,
        }

    async def vacancy_gaps(vacancy_id: str) -> dict[str, Any]:
        """Считает разрывы между вакансией и профилем пользователя."""
        report = await compute_gaps(session, user_id, _as_uuid(vacancy_id, "vacancy_id"))
        return {
            "vacancy_id": str(report.vacancy_id),
            "overall_readiness": report.overall_readiness,
            "coverage_all": report.coverage_all,
            "confirmed_readiness": report.confirmed_readiness,
            "provisional_count": report.provisional_count,
            "provisional_weight": report.provisional_weight,
            "confirmed_weight": report.confirmed_weight,
            "critical_count": report.critical_count,
            "critical_weight": report.critical_weight,
            "critical_gap_count": report.critical_gap_count,
            "unmatched_count": report.unmatched_count,
            "items": [
                {
                    "skill_name": item.skill_name,
                    "topic_key": item.topic_key,
                    "topic_status": item.topic_status,
                    "requirement_group": item.requirement_group,
                    "requirement_logic": item.requirement_logic,
                    "criticality": item.criticality,
                    "required_level": item.required_level,
                    "user_level": item.user_level,
                    "gap": item.gap,
                    "satisfied": item.satisfied,
                }
                for item in report.items
            ],
        }

    return [
        ToolDefinition(
            name="extract_vacancy_requirements",
            description=(
                "Извлекает требования из текста вакансии: название, компанию, уровень "
                "и список навыков с требуемым уровнем 0..100. Ничего не сохраняет в БД."
            ),
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Полный текст вакансии"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            handler=extract_vacancy,
        ),
        ToolDefinition(
            name="extract_resume_skills",
            description=(
                "Извлекает навыки и опыт из текста резюме: навыки с уровнем владения "
                "0..100, годы опыта и самооценку. Ничего не сохраняет в БД."
            ),
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Полный текст резюме"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            handler=extract_resume,
        ),
        ToolDefinition(
            name="get_vacancy_requirements",
            description=(
                "Возвращает требования сохранённой вакансии текущего пользователя "
                "по её идентификатору."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "vacancy_id": {
                        "type": "string",
                        "description": "UUID вакансии пользователя",
                    }
                },
                "required": ["vacancy_id"],
                "additionalProperties": False,
            },
            handler=vacancy_requirements,
        ),
        ToolDefinition(
            name="get_user_skill_state",
            description=(
                "Возвращает профиль знаний текущего пользователя: уровень по темам "
                "онтологии и навыки вне онтологии. Пользователь определяется сессией."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            handler=user_skill_state,
        ),
        ToolDefinition(
            name="query_skill_dependencies",
            description=(
                "Возвращает прямые пререквизиты и зависимые темы для указанных тем графа знаний."
            ),
            parameters=_TOPIC_KEYS_SCHEMA,
            handler=skill_dependencies,
        ),
        ToolDefinition(
            name="update_skill_proficiency",
            description=(
                "Обновляет оценку владения темой в профиле текущего пользователя. "
                "Вызывай только при наличии подтверждения от пользователя."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "topic_key": {"type": "string", "description": "Ключ темы онтологии"},
                    "score": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Новый уровень владения темой",
                    },
                    "evidence": {
                        "type": ["string", "null"],
                        "description": "Чем подтверждена оценка",
                    },
                },
                "required": ["topic_key", "score"],
                "additionalProperties": False,
            },
            handler=update_proficiency,
        ),
        ToolDefinition(
            name="compute_vacancy_gaps",
            description=(
                "Считает разрывы между требованиями вакансии и профилем пользователя, "
                "а также общую готовность к вакансии (0..1)."
            ),
            parameters={
                "type": "object",
                "properties": {"vacancy_id": {"type": "string", "description": "UUID вакансии"}},
                "required": ["vacancy_id"],
                "additionalProperties": False,
            },
            handler=vacancy_gaps,
        ),
    ]


def register_analysis_tools(
    registry: ToolRegistry,
    session: AsyncSession,
    provider: LLMProvider,
    *,
    user_id: uuid.UUID,
    embedder: EmbeddingProvider | None = None,
) -> None:
    """Регистрирует инструменты анализа в реестре агента."""
    for tool in build_analysis_tools(session, provider, user_id=user_id, embedder=embedder):
        registry.register(tool)


def _skill_payload(skill: SkillEntry) -> dict[str, Any]:
    """Навык в виде, удобном для LLM."""
    return {
        "name": skill.raw_name,
        "topic_key": skill.topic.key if skill.topic is not None else None,
        "level": skill.level,
        "confidence": skill.confidence,
        "match_method": skill.match_method,
        "requirement_group": skill.requirement_group,
        "requirement_logic": skill.requirement_logic,
        "criticality": skill.criticality,
    }


def _as_uuid(value: str, field: str) -> uuid.UUID:
    """Разбирает UUID из аргумента инструмента с понятной ошибкой."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{field} должен быть UUID, получено: {value!r}") from exc
