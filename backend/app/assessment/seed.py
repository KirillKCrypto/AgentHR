"""Идемпотентный сид банка вопросов assessment."""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment.questions import ASSESSMENT_QUESTIONS
from app.assessment.questions_extra import EXTRA_QUESTIONS
from app.db.session import async_session_factory
from app.models import AssessmentQuestion, Topic


async def seed_assessment_questions(session: AsyncSession) -> int:
    """Синхронизирует банк вопросов по ключу. Возвращает число изменённых вопросов."""
    all_questions = (*ASSESSMENT_QUESTIONS, *EXTRA_QUESTIONS)
    topic_keys = {spec.topic_key for spec in all_questions}
    topics = {
        topic.key: topic
        for topic in (await session.scalars(select(Topic).where(Topic.key.in_(topic_keys)))).all()
    }
    missing = sorted(topic_keys - topics.keys())
    if missing:
        raise RuntimeError(f"Для assessment нет тем онтологии: {missing}")

    existing = {
        question.key: question
        for question in (
            await session.scalars(
                select(AssessmentQuestion).where(
                    AssessmentQuestion.key.in_([spec.key for spec in all_questions])
                )
            )
        ).all()
    }

    changed = 0
    for spec in all_questions:
        topic = topics[spec.topic_key]
        question = existing.get(spec.key)
        options = [{"key": key, "text": text} for key, text in spec.options]
        if question is None:
            session.add(
                AssessmentQuestion(
                    key=spec.key,
                    topic_id=topic.id,
                    difficulty=spec.difficulty,
                    kind="single_choice",
                    prompt=spec.prompt,
                    options=options,
                    correct_key=spec.correct_key,
                    explanation=spec.explanation,
                    status="active",
                )
            )
            changed += 1
            continue

        if (
            question.topic_id != topic.id
            or question.difficulty != spec.difficulty
            or question.prompt != spec.prompt
            or question.options != options
            or question.correct_key != spec.correct_key
            or question.explanation != spec.explanation
            or question.status != "active"
        ):
            question.topic_id = topic.id
            question.difficulty = spec.difficulty
            question.prompt = spec.prompt
            question.options = options
            question.correct_key = spec.correct_key
            question.explanation = spec.explanation
            question.status = "active"
            changed += 1

    await session.commit()
    return changed


async def main() -> None:
    """CLI: заполнить банк вопросов."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    async with async_session_factory() as session:
        changed = await seed_assessment_questions(session)
    print(f"Assessment: обновлено вопросов: {changed}")


if __name__ == "__main__":
    asyncio.run(main())
