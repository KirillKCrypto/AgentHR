"""CLI наполнения банка вопросов.

Примеры:
    uv run python -m app.questions.seed --dry-run
    uv run python -m app.questions.seed --all
    uv run python -m app.questions.seed --topics oop,algorithms --difficulties 1,3,5

Генерация идемпотентна: повторный запуск добирает только недостающие вопросы.
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.llm.factory import create_llm_provider
from app.models import Topic
from app.questions.generator import generate_questions
from app.services.questions import add_questions, count_by_difficulty

# Оценка на один вызов LLM: промпт темы + JSON со списком вопросов.
TOKENS_PER_CALL = 1200


def _parser() -> argparse.ArgumentParser:
    """Собирает аргументы CLI."""
    parser = argparse.ArgumentParser(description="Наполнение банка вопросов AgentHR")
    parser.add_argument("--all", action="store_true", help="все canonical-темы")
    parser.add_argument(
        "--include-auto",
        action="store_true",
        help="включить auto-canonical темы (по умолчанию только темы пакета)",
    )
    parser.add_argument(
        "--topics",
        default="",
        help="ключи тем через запятую; пусто — все темы с --all",
    )
    parser.add_argument(
        "--difficulties",
        default="1,3,5",
        help="сложности через запятую (1–5), по умолчанию 1,3,5",
    )
    parser.add_argument("--per-topic", type=int, default=5, help="вопросов на тему и сложность")
    parser.add_argument("--limit", type=int, default=None, help="максимум LLM-вызовов за прогон")
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="повторы одного вызова при таймауте или ошибке сети",
    )
    parser.add_argument("--dry-run", action="store_true", help="только оценить объём")
    return parser


async def _run(args: argparse.Namespace) -> int:
    """Выполняет наполнение банка."""
    difficulties = [int(value) for value in args.difficulties.split(",") if value.strip()]
    if not difficulties or any(value < 1 or value > 5 for value in difficulties):
        print("Сложности должны быть числами 1–5", file=sys.stderr)
        return 1

    keys = [key.strip() for key in args.topics.split(",") if key.strip()]
    async with async_session_factory() as session:
        statement = select(Topic).where(Topic.status == "canonical").order_by(Topic.key)
        if not keys and not args.include_auto:
            statement = statement.where(Topic.origin == "seed")
        if keys:
            statement = statement.where(Topic.key.in_(keys))
        topics = (await session.scalars(statement)).all()
        if not topics:
            print("Темы не найдены", file=sys.stderr)
            return 1

        plan: list[tuple[Topic, int, int]] = []
        for topic in topics:
            for difficulty in difficulties:
                existing = await count_by_difficulty(session, topic.id, difficulty)
                missing = max(0, args.per_topic - existing)
                if missing:
                    plan.append((topic, difficulty, missing))

        if args.limit is not None:
            plan = plan[: max(0, args.limit)]

        if args.dry_run:
            calls = len(plan)
            print(
                f"Тем: {len(topics)}; сложностей: {len(difficulties)}; вызовов: {calls}; "
                f"вопросов: {sum(missing for _, _, missing in plan)}; "
                f"~токенов: {calls * TOKENS_PER_CALL:,}"
            )
            return 0

        settings = get_settings()
        provider = create_llm_provider(settings)
        inserted = 0
        calls = 0
        failed = 0
        try:
            for topic, difficulty, missing in plan:
                questions: list[dict] = []
                for attempt in range(max(1, args.retries + 1)):
                    questions = await generate_questions(provider, topic, difficulty, missing)
                    if questions:
                        break
                    if attempt < args.retries:
                        await asyncio.sleep(2 * (attempt + 1))
                calls += 1
                if not questions:
                    failed += 1
                    continue
                added = await add_questions(session, topic.id, difficulty, questions)
                await session.commit()
                inserted += added
                print(f"{topic.key} d{difficulty}: +{added} (запрошено {missing})")
        finally:
            await provider.close()

    print(
        f"Готово: вызовов {calls}, добавлено вопросов {inserted}, "
        f"неудачных вызовов {failed}"
    )
    return 0


def main() -> None:
    """Точка входа CLI."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
