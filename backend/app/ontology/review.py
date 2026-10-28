"""CLI ревью provisional-тем онтологии.

Примеры:
    uv run python -m app.ontology.review list
    uv run python -m app.ontology.review approve auto-docker-...
    uv run python -m app.ontology.review reject auto-docker-...
    uv run python -m app.ontology.review merge auto-docker-... --into docker
"""

import argparse
import asyncio
import sys

from app.db.session import async_session_factory
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
