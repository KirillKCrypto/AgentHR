"""CLI ревью provisional-тем онтологии.

Примеры:
    uv run python -m app.ontology.review list
    uv run python -m app.ontology.review auto
    uv run python -m app.ontology.review approve auto-docker-...
    uv run python -m app.ontology.review reject auto-docker-...
    uv run python -m app.ontology.review merge auto-docker-... --into docker
"""

import argparse
import asyncio
import sys

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.embeddings import create_embedding_provider
from app.llm.factory import create_llm_provider
from app.services.ontology_auto_review import auto_review_topics
from app.services.ontology_review import (
    ReviewError,
    approve_topic,
    list_review_topics,
    merge_topics,
    reject_topic,
)


async def _run(args: argparse.Namespace) -> int:
    """Выполняет выбранную команду."""
    async with async_session_factory() as session:
        if args.command == "list":
            topics = await list_review_topics(session, status=args.status)
            if not topics:
                print(f"Тем со статусом {args.status!r} нет")
                return 0
            for topic in topics:
                print(
                    f"{topic.key}\t{topic.status}\t"
                    f"skills={topic.skill_count}\tcandidates={topic.candidate_count}\t"
                    f"{topic.name}"
                )
            return 0

        if args.command == "auto":
            return await _run_auto(session, args)

        try:
            if args.command == "approve":
                topic = await approve_topic(session, args.key, actor=args.actor)
                await session.commit()
                print(f"Тема {topic.key!r} подтверждена (canonical)")
                return 0

            if args.command == "reject":
                topic = await reject_topic(session, args.key, actor=args.actor)
                await session.commit()
                print(f"Тема {topic.key!r} отклонена (rejected)")
                return 0

            if args.command == "merge":
                source, target = await merge_topics(
                    session,
                    args.key,
                    args.into,
                    actor=args.actor,
                )
                await session.commit()
                print(f"Тема {source.key!r} объединена с {target.key!r} (merged)")
                return 0
        except ReviewError as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            return 1

    return 1


async def _run_auto(session, args: argparse.Namespace) -> int:
    """Пакетно проверяет все provisional-темы теми же правилами и LLM."""
    topics = await list_review_topics(session, status="provisional")
    if not topics:
        print("Provisional-тем нет")
        return 0

    settings = get_settings()
    if args.limit is not None:
        settings = settings.model_copy(
            update={"ontology_auto_review_max_topics": max(0, args.limit)}
        )

    provider = create_llm_provider(settings)
    embedder = create_embedding_provider(settings)
    try:
        decisions = await auto_review_topics(
            session,
            [topic.id for topic in topics],
            provider=provider,
            embedder=embedder,
            settings=settings,
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001 — CLI должен показать причину, а не traceback
        await session.rollback()
        print(f"Ошибка авто-ревью: {exc}", file=sys.stderr)
        return 1
    finally:
        await provider.close()

    if not decisions:
        print("Новых данных для авто-ревью нет")
        return 0
    for decision in decisions:
        target = f" -> {decision.target_key}" if decision.target_key else ""
        print(
            f"{decision.topic_key}\t{decision.action}{target}\t"
            f"confidence={decision.confidence:.2f}\tsource={decision.source}\t"
            f"{decision.reason}"
        )
    return 0


def _parser() -> argparse.ArgumentParser:
    """Собирает CLI-парсер."""
    parser = argparse.ArgumentParser(description="Ревью provisional-тем онтологии AgentHR")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="показать темы")
    list_parser.add_argument(
        "--status",
        default="provisional",
        choices=("canonical", "provisional", "merged", "rejected"),
    )

    auto_parser = subparsers.add_parser(
        "auto", help="автоматически проверить все provisional-темы"
    )
    auto_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="максимум тем за прогон (по умолчанию из настроек)",
    )

    for command, help_text in (
        ("approve", "подтвердить provisional-тему"),
        ("reject", "отклонить пустую provisional-тему"),
        ("merge", "объединить provisional-тему с целевой"),
    ):
        sub = subparsers.add_parser(command, help=help_text)
        sub.add_argument("key", help="ключ темы")
        sub.add_argument("--actor", default="cli", help="кто выполняет действие")
        if command == "merge":
            sub.add_argument("--into", required=True, help="ключ целевой темы")

    return parser


def main() -> None:
    """Тонкая CLI-обёртка над async-сервисом ревью."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
