"""Идемпотентный сид онтологии v1 в БД.

Запуск: `uv run python -m app.ontology.seed`.

Повторный запуск не дублирует данные: темы обновляются по ключу,
рёбра `REQUIRES` синхронизируются точно (только между засеянными темами).
Темы, созданные автоматически из кандидатов, сид не трогает.
"""

import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models import Topic, TopicPrerequisite
from app.ontology.topics import ONTOLOGY_TOPICS, ONTOLOGY_VERSION


@dataclass
class SeedResult:
    """Итог сида онтологии."""

    topics_created: int = 0
    topics_updated: int = 0
    edges_created: int = 0
    edges_removed: int = 0

    def summary(self) -> str:
        """Краткая сводка для CLI и логов."""
        return (
            f"темы: +{self.topics_created} новых, {self.topics_updated} обновлено; "
            f"связи: +{self.edges_created}, -{self.edges_removed}"
        )


async def seed_ontology(session: AsyncSession, *, version: int = ONTOLOGY_VERSION) -> SeedResult:
    """Приводит онтологию в БД к состоянию пакета онтологии.

    Операция идемпотентна: повторный вызов не меняет количество строк.
    """
    result = SeedResult()
    keys = [topic.key for topic in ONTOLOGY_TOPICS]

    existing = {
        topic.key: topic
        for topic in (await session.scalars(select(Topic).where(Topic.key.in_(keys)))).all()
    }

    seeded_ids: dict[str, Topic] = {}
    for definition in ONTOLOGY_TOPICS:
        topic = existing.get(definition.key)
        if topic is None:
            topic = Topic(
                key=definition.key,
                name=definition.name,
                description=definition.description,
                category=definition.category,
                aliases=list(definition.aliases),
                ontology_version=version,
                is_auto_generated=False,
            )
            session.add(topic)
            result.topics_created += 1
        else:
            changed = (
                topic.name != definition.name
                or topic.description != definition.description
                or topic.category != definition.category
                or list(topic.aliases or []) != list(definition.aliases)
                or topic.ontology_version != version
                or topic.is_auto_generated
            )
            topic.name = definition.name
            topic.description = definition.description
            topic.category = definition.category
            topic.aliases = list(definition.aliases)
            topic.ontology_version = version
            topic.is_auto_generated = False
            if changed:
                result.topics_updated += 1
        seeded_ids[definition.key] = topic

    await session.flush()

    desired_edges = {
        (definition.key, prerequisite)
        for definition in ONTOLOGY_TOPICS
        for prerequisite in definition.prerequisites
    }

    seeded_topic_ids = [topic.id for topic in seeded_ids.values()]
    current_edges = (
        await session.scalars(
            select(TopicPrerequisite).where(
                TopicPrerequisite.topic_id.in_(seeded_topic_ids),
                TopicPrerequisite.prerequisite_id.in_(seeded_topic_ids),
            )
        )
    ).all()

    id_to_key = {topic.id: key for key, topic in seeded_ids.items()}
    current_pairs = {
        (id_to_key[edge.topic_id], id_to_key[edge.prerequisite_id]) for edge in current_edges
    }

    for edge in current_edges:
        pair = (id_to_key[edge.topic_id], id_to_key[edge.prerequisite_id])
        if pair not in desired_edges:
            await session.delete(edge)
            result.edges_removed += 1

    for topic_key, prerequisite_key in sorted(desired_edges - current_pairs):
        session.add(
            TopicPrerequisite(
                topic_id=seeded_ids[topic_key].id,
                prerequisite_id=seeded_ids[prerequisite_key].id,
            )
        )
        result.edges_created += 1

    await session.commit()
    return result


async def main() -> None:
    """Точка входа CLI: засевает онтологию в БД."""
    # Кириллица в выводе Windows-консоли: принудительно UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    async with async_session_factory() as session:
        result = await seed_ontology(session)
    print(f"Онтология v{ONTOLOGY_VERSION}: {result.summary()}")


if __name__ == "__main__":
    asyncio.run(main())
