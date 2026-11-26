"""Пересборка профилей после миграции на активное резюме.

Запуск:
    uv run python -m app.maintenance.rebuild_profiles
"""

import asyncio

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models import User
from app.services.profile import rebuild_profile


async def rebuild_all() -> int:
    """Пересобирает профили и планы всех пользователей."""
    async with async_session_factory() as session:
        user_ids = (await session.scalars(select(User.id).order_by(User.id))).all()
        for user_id in user_ids:
            await rebuild_profile(session, user_id)
        return len(user_ids)


async def main() -> None:
    count = await rebuild_all()
    print(f"Пересобрано профилей: {count}.")


if __name__ == "__main__":
    asyncio.run(main())
