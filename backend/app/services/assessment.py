"""Мини-тесты навыков: старт, ответы, детерминированный скоринг."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentQuestion,
    Topic,
    UserSkillState,
)

QUESTIONS_PER_ATTEMPT = 10
QUESTIONS_PER_DIFFICULTY = 2
DIFFICULTIES = (20, 40, 60, 75, 90)


class AssessmentNotFound(Exception):
    """Тема, попытка или вопрос не найдены."""


class AssessmentStateError(Exception):
    """Операция недопустима для текущего состояния попытки."""


class AssessmentValidationError(Exception):
    """Некорректный ответ или вопрос вне попытки."""


async def list_available_topics(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Темы с вопросами и статусом прохождения для пользователя."""
    rows = (
        await session.execute(
            select(Topic.id, Topic.key, Topic.name, func.count(AssessmentQuestion.id))
            .join(AssessmentQuestion, AssessmentQuestion.topic_id == Topic.id)
            .where(AssessmentQuestion.status == "active")
            .group_by(Topic.id, Topic.key, Topic.name)
            .order_by(Topic.key)
        )
    ).all()
    completed = {
        attempt.topic_id: attempt
        for attempt in (
            await session.scalars(
                select(AssessmentAttempt).where(
                    AssessmentAttempt.user_id == user_id,
                    AssessmentAttempt.status == "completed",
                )
            )
        ).all()
    }
    result: list[dict[str, Any]] = []
    for topic_id, key, name, count in rows:
        attempt = completed.get(topic_id)
        result.append(
            {
                "topic_key": key,
                "topic_name": name,
                "question_count": count,
                "completed": attempt is not None,
                "test_level": attempt.test_level if attempt is not None else None,
                "attempt_id": attempt.id if attempt is not None else None,
            }
        )
    return result


async def start_assessment(
    session: AsyncSession,
    user_id: uuid.UUID,
    topic_key: str,
) -> tuple[AssessmentAttempt, list[AssessmentQuestion]]:
    """Возвращает активную попытку или создаёт новую."""
    topic = await session.scalar(select(Topic).where(Topic.key == topic_key))
    if topic is None:
        raise AssessmentNotFound(f"Тема {topic_key!r} не найдена")

    completed = await session.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.topic_id == topic.id,
            AssessmentAttempt.status == "completed",
        )
    )
    if completed is not None:
        raise AssessmentStateError("Тест по этой теме уже пройден")

    attempt = await session.scalar(
        select(AssessmentAttempt)
        .where(
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.topic_id == topic.id,
            AssessmentAttempt.status == "in_progress",
        )
        .order_by(AssessmentAttempt.started_at.desc())
    )
    if attempt is not None:
        questions = await _load_attempt_questions(session, attempt)
        if questions:
            return attempt, questions

    questions = await _select_questions(session, topic.id)
    if not questions:
        raise AssessmentNotFound(f"Для темы {topic_key!r} нет вопросов")

    attempt = AssessmentAttempt(
        user_id=user_id,
        topic_id=topic.id,
        status="in_progress",
        question_ids=[str(question.id) for question in questions],
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return attempt, list(questions)


async def answer_question(
    session: AsyncSession,
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    answer_key: str,
) -> tuple[int, int]:
    """Принимает ответ; возвращает (отвечено, всего)."""
    attempt = await _load_attempt(session, user_id, attempt_id)
    if attempt.status != "in_progress":
        raise AssessmentStateError("Попытка уже завершена")
    if str(question_id) not in attempt.question_ids:
        raise AssessmentValidationError("Вопрос не относится к этой попытке")

    existing = await session.scalar(
        select(AssessmentAnswer).where(
            AssessmentAnswer.attempt_id == attempt.id,
            AssessmentAnswer.question_id == question_id,
        )
    )
    if existing is not None:
        raise AssessmentStateError("На этот вопрос уже дан ответ")

    question = await session.get(AssessmentQuestion, question_id)
    if question is None:
        raise AssessmentNotFound("Вопрос не найден")
    allowed = {str(option.get("key")) for option in question.options if isinstance(option, dict)}
    if answer_key not in allowed:
        raise AssessmentValidationError("Ответ не соответствует вариантам вопроса")

    session.add(
        AssessmentAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            answer_key=answer_key,
            is_correct=answer_key == question.correct_key,
            score=1.0 if answer_key == question.correct_key else 0.0,
        )
    )
    await session.commit()

    answered = await session.scalar(
        select(func.count())
        .select_from(AssessmentAnswer)
        .where(AssessmentAnswer.attempt_id == attempt.id)
    )
    return int(answered or 0), len(attempt.question_ids)


async def finish_assessment(
    session: AsyncSession,
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
) -> dict[str, Any]:
    """Завершает попытку и обновляет verified level в профиле."""
    attempt = await _load_attempt(session, user_id, attempt_id)
    if attempt.status == "completed":
        return await _build_result(session, attempt)

    questions = await _load_attempt_questions(session, attempt)
    if not questions:
        raise AssessmentStateError("В попытке нет вопросов")
    answers = (
        await session.scalars(
            select(AssessmentAnswer).where(AssessmentAnswer.attempt_id == attempt.id)
        )
    ).all()
    if not answers:
        raise AssessmentStateError("Нет ответов для завершения")

    answers_by_question = {answer.question_id: answer for answer in answers}
    max_points = sum(question.difficulty for question in questions)
    earned = sum(
        question.difficulty
        for question in questions
        if answers_by_question.get(question.id) is not None
        and answers_by_question[question.id].is_correct
    )
    score = earned / max_points if max_points else 0.0
    test_level = max(0, min(100, round(20 + 75 * score)))
    confidence = min(0.95, 0.5 + 0.09 * len(answers))

    attempt.status = "completed"
    attempt.score = round(score, 4)
    attempt.test_level = test_level
    attempt.confidence = round(confidence, 3)
    attempt.finished_at = datetime.now(UTC)

    await _update_skill_state(
        session, user_id, attempt, test_level, confidence, len(answers), len(questions)
    )
    await session.commit()
    return await _build_result(session, attempt)


async def _select_questions(
    session: AsyncSession,
    topic_id: uuid.UUID,
) -> list[AssessmentQuestion]:
    """Выбирает по 2 вопроса каждой сложности для одной попытки."""
    selected: list[AssessmentQuestion] = []
    for difficulty in DIFFICULTIES:
        rows = (
            await session.scalars(
                select(AssessmentQuestion)
                .where(
                    AssessmentQuestion.topic_id == topic_id,
                    AssessmentQuestion.status == "active",
                    AssessmentQuestion.difficulty == difficulty,
                )
                .order_by(AssessmentQuestion.key)
                .limit(QUESTIONS_PER_DIFFICULTY)
            )
        ).all()
        selected.extend(rows)
    return selected[:QUESTIONS_PER_ATTEMPT]


async def _load_attempt(
    session: AsyncSession,
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
) -> AssessmentAttempt:
    """Загружает попытку пользователя."""
    attempt = await session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.user_id != user_id:
        raise AssessmentNotFound("Попытка не найдена")
    return attempt


async def _load_attempt_questions(
    session: AsyncSession,
    attempt: AssessmentAttempt,
) -> list[AssessmentQuestion]:
    """Загружает вопросы попытки в сохранённом порядке."""
    ids = [uuid.UUID(value) for value in attempt.question_ids]
    if not ids:
        return []
    questions = (
        await session.scalars(select(AssessmentQuestion).where(AssessmentQuestion.id.in_(ids)))
    ).all()
    by_id = {question.id: question for question in questions}
    return [by_id[question_id] for question_id in ids if question_id in by_id]


async def _update_skill_state(
    session: AsyncSession,
    user_id: uuid.UUID,
    attempt: AssessmentAttempt,
    test_level: int,
    confidence: float,
    answered: int,
    total: int,
) -> None:
    """Сохраняет verified level и evidence теста в срезе профиля."""
    state = await session.scalar(
        select(UserSkillState).where(
            UserSkillState.user_id == user_id,
            UserSkillState.topic_id == attempt.topic_id,
        )
    )
    if state is None:
        state = UserSkillState(
            user_id=user_id,
            topic_id=attempt.topic_id,
            claimed_level=0,
            evidence_strength=0.9,
        )
        session.add(state)

    if state.claimed_level is None:
        state.claimed_level = state.proficiency
    state.verified_level = test_level
    state.proficiency = test_level
    state.confidence = confidence
    state.evidence_strength = 0.9
    state.source = "assessment"
    state.last_assessed = datetime.now(UTC)
    state.evidence = list(state.evidence or [])[-9:] + [
        {
            "type": "assessment",
            "attempt_id": str(attempt.id),
            "level": test_level,
            "confidence": round(confidence, 3),
            "correct": answered,
            "total": total,
        }
    ]


async def _build_result(session: AsyncSession, attempt: AssessmentAttempt) -> dict[str, Any]:
    """Собирает результат попытки с разбором ответов."""
    questions = await _load_attempt_questions(session, attempt)
    answers = {
        answer.question_id: answer
        for answer in (
            await session.scalars(
                select(AssessmentAnswer).where(AssessmentAnswer.attempt_id == attempt.id)
            )
        ).all()
    }
    topic = await session.get(Topic, attempt.topic_id)
    items = []
    for question in questions:
        answer = answers.get(question.id)
        items.append(
            {
                "question_id": question.id,
                "prompt": question.prompt,
                "answer_key": answer.answer_key if answer is not None else None,
                "correct_key": question.correct_key,
                "is_correct": bool(answer and answer.is_correct),
                "explanation": question.explanation,
            }
        )
    return {
        "attempt": attempt,
        "topic_key": topic.key if topic is not None else None,
        "topic_name": topic.name if topic is not None else None,
        "items": items,
        "correct_count": sum(1 for item in items if item["is_correct"]),
        "total": len(items),
    }
