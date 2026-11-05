"""CLI: перемешать уже сохранённые варианты ответов.

Нужен один раз для вопросов, сгенерированных до защиты от смещения правильного
ответа к варианту A: ``python -m app.questions.shuffle``.
"""

import asyncio
import sys

from app.db.session import async_session_factory
from app.questions.quiz import shuffle_existing_options


async def main() -> None:
    """Перемешивает варианты и фиксирует результат в БД."""
    async with async_session_factory() as session:
        changed = await shuffle_existing_options(session)
        await session.commit()
    print(f"Перемешано вопросов: {changed}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
