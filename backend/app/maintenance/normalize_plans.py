"""Нормализация планов: один активный план на резюме и вакансию.

Запуск:
    uv run python -m app.maintenance.normalize_plans --dry-run
    uv run python -m app.maintenance.normalize_plans
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models import LearningPlan, Resume


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Оставить один активный план на резюме")
    parser.add_argument("--dry-run", action="store_true", help="Только показать план")
    return parser


async def normalize(dry_run: bool) -> tuple[int, int]:
    """Возвращает число просмотренных и архивированных планов."""
    async with async_session_factory() as session:
        resume_rows = (await session.execute(select(Resume.user_id, Resume.id))).all()
        resumes_by_user: dict[uuid.UUID, set[uuid.UUID]] = {}
        for user_id, resume_id in resume_rows:
            resumes_by_user.setdefault(user_id, set()).add(resume_id)

        plans = (
            await session.scalars(
                select(LearningPlan).order_by(LearningPlan.created_at.desc())
            )
        ).all()

        to_archive: list[LearningPlan] = []
        winners: list[LearningPlan] = []
        seen: set[tuple[uuid.UUID, uuid.UUID | None, uuid.UUID | None]] = set()
        for plan in plans:
            known_resumes = resumes_by_user.get(plan.user_id, set())
            if plan.resume_id is None or plan.resume_id not in known_resumes:
                to_archive.append(plan)
                continue
            key = (plan.user_id, plan.resume_id, plan.vacancy_id)
            if key in seen:
                to_archive.append(plan)
                continue
            seen.add(key)
            winners.append(plan)

        to_archive = [plan for plan in to_archive if plan.status == "active"]
        if not dry_run:
            for plan in winners:
                plan.status = "active"
            for plan in to_archive:
                plan.status = "archived"
            await session.commit()

        return len(plans), len(to_archive)


async def main() -> None:
    args = _parser().parse_args()
    total, archived = await normalize(args.dry_run)
    mode = "будет архивировано" if args.dry_run else "архивировано"
    print(f"Проверено планов: {total}. {mode}: {archived}.")


if __name__ == "__main__":
    asyncio.run(main())
