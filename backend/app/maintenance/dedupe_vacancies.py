"""Удаление дублей вакансий без потери истории.

Запуск:
    uv run python -m app.maintenance.dedupe_vacancies --dry-run
    uv run python -m app.maintenance.dedupe_vacancies
"""

import argparse
import asyncio
import uuid

from sqlalchemy import delete, func, select

from app.db.session import async_session_factory
from app.models import InterviewSession, LearningPlan, Vacancy
from app.services.content_hash import content_hash


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Удалить дубли вакансий без интервью и планов")
    parser.add_argument("--dry-run", action="store_true", help="Только показать план")
    return parser


async def _references(session, vacancy_id: uuid.UUID) -> int:
    interviews = await session.scalar(
        select(func.count())
        .select_from(InterviewSession)
        .where(InterviewSession.vacancy_id == vacancy_id)
    )
    plans = await session.scalar(
        select(func.count())
        .select_from(LearningPlan)
        .where(LearningPlan.vacancy_id == vacancy_id)
    )
    return int(interviews or 0) + int(plans or 0)


async def dedupe(dry_run: bool) -> tuple[int, int]:
    """Возвращает число просмотренных и удалённых вакансий."""
    async with async_session_factory() as session:
        vacancies = (await session.scalars(select(Vacancy))).all()
        groups: dict[tuple[uuid.UUID, str], list[Vacancy]] = {}
        for vacancy in vacancies:
            digest = vacancy.content_hash or content_hash(vacancy.raw_text)
            groups.setdefault((vacancy.user_id, digest), []).append(vacancy)

        to_delete: list[Vacancy] = []
        for group in groups.values():
            if len(group) < 2:
                continue
            ordered = sorted(group, key=lambda item: item.created_at)
            keep = ordered[0]
            for candidate in ordered:
                if await _references(session, candidate.id) > 0:
                    keep = candidate
                    break
            for candidate in ordered:
                if candidate.id == keep.id:
                    continue
                if await _references(session, candidate.id) == 0:
                    to_delete.append(candidate)

        if to_delete and not dry_run:
            await session.execute(
                delete(Vacancy).where(Vacancy.id.in_([item.id for item in to_delete]))
            )
            await session.commit()

        return len(vacancies), len(to_delete)


async def main() -> None:
    args = _parser().parse_args()
    total, removed = await dedupe(args.dry_run)
    mode = "будет удалено" if args.dry_run else "удалено"
    print(f"Проверено вакансий: {total}. {mode}: {removed}.")


if __name__ == "__main__":
    asyncio.run(main())
