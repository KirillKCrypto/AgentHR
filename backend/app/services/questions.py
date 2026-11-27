"""Банк вопросов: добавление, выборка и счётчики."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMProvider
from app.models import Question, Topic, TopicTestResult, UserSkillState
from app.questions.generator import generate_questions
from app.services.normalization import normalize_name
from app.services.review import next_review


@dataclass(frozen=True)
class QuestionItem:
    """Вопрос банка для ответа API и тренировки."""

    id: uuid.UUID
    topic_id: uuid.UUID
    difficulty: int
    text: str
    expected_points: tuple[str, ...]
    source: str


def fingerprint(topic_id: uuid.UUID, difficulty: int, text: str) -> str:
    """Стабильный хеш вопроса: тема, сложность и текст без регистра."""
    normalized = normalize_name(text)
    return hashlib.sha256(f"{topic_id}:{difficulty}:{normalized}".encode()).hexdigest()


def clean_points(values: Any) -> list[str]:
    """Оставляет непустые эталонные пункты."""
    if not isinstance(values, (list, tuple)):
        return []
    return [str(value).strip() for value in values if str(value).strip()][:8]


async def add_questions(
    session: AsyncSession,
    topic_id: uuid.UUID,
    difficulty: int,
    questions: list[dict[str, Any]],
    *,
    source: str = "llm",
) -> int:
    """Добавляет вопросы без дублей; возвращает число новых строк."""
    inserted = 0
    for item in questions:
        text = " ".join(str(item.get("text") or "").split())
        if len(text) < 10:
            continue
        statement = (
            pg_insert(Question)
            .values(
                topic_id=topic_id,
                difficulty=difficulty,
                text=text,
                expected_points=clean_points(item.get("expected_points")),
                source=source,
                fingerprint=fingerprint(topic_id, difficulty, text),
            )
            .on_conflict_do_nothing(index_elements=[Question.fingerprint])
        )
        result = await session.execute(statement)
        inserted += result.rowcount or 0
    return inserted


async def count_by_difficulty(
    session: AsyncSession,
    topic_id: uuid.UUID,
    difficulty: int,
) -> int:
    """Сколько вопросов уже есть по теме и сложности."""
    return (
        await session.scalar(
            select(func.count())
            .select_from(Question)
            .where(Question.topic_id == topic_id, Question.difficulty == difficulty)
        )
    ) or 0


async def count_by_topic(
    session: AsyncSession,
    topic_ids: list[uuid.UUID],
) -> dict[uuid.UUID, int]:
    """Счётчики вопросов по списку тем одним запросом."""
    if not topic_ids:
        return {}
    rows = (
        await session.execute(
            select(Question.topic_id, func.count())
            .where(Question.topic_id.in_(topic_ids))
            .group_by(Question.topic_id)
        )
    ).all()
    return {topic_id: count for topic_id, count in rows}


async def pick_questions(
    session: AsyncSession,
    topic_id: uuid.UUID,
    *,
    difficulty: int | None = None,
    limit: int = 5,
    exclude_ids: set[uuid.UUID] | None = None,
) -> tuple[QuestionItem, ...]:
    """Случайная выборка вопросов по теме; при малом пуле хватает ORDER BY random()."""
    statement = select(Question).where(Question.topic_id == topic_id)
    if difficulty is not None:
        statement = statement.where(Question.difficulty == difficulty)
    if exclude_ids:
        statement = statement.where(Question.id.not_in(exclude_ids))
    rows = (
        await session.scalars(statement.order_by(func.random()).limit(max(1, limit)))
    ).all()
    return tuple(
        QuestionItem(
            id=row.id,
            topic_id=row.topic_id,
            difficulty=row.difficulty,
            text=row.text,
            expected_points=tuple(row.expected_points or ()),
            source=row.source,
        )
        for row in rows
    )


async def ensure_question_bank(
    session: AsyncSession,
    topic: Topic,
    *,
    count: int = 10,
    provider: LLMProvider | None = None,
) -> int:
    """Добирает банк темы до нужного числа вопросов через LLM.

    Возвращает число добавленных вопросов. Сбой генерации не роняет тест:
    маршрут использует то, что уже есть в банке.
    """
    if provider is None:
        return 0
    base, remainder = divmod(max(1, count), 5)
    added = 0
    for difficulty in range(1, 6):
        wanted = base + (1 if difficulty <= remainder else 0)
        existing = await count_by_difficulty(session, topic.id, difficulty)
        missing = max(0, wanted - existing)
        if missing == 0:
            continue
        for _ in range(2):
            generated = await generate_questions(provider, topic, difficulty, missing)
            if generated:
                added += await add_questions(session, topic.id, difficulty, generated)
                break
    return added


async def pick_test_questions(
    session: AsyncSession,
    topic_id: uuid.UUID,
    *,
    count: int = 10,
) -> tuple[QuestionItem, ...]:
    """Собирает тест из вопросов разной сложности.

    По умолчанию 10 вопросов: по два с каждой сложности 1–5. Если на какой-то
    сложности вопросов не хватает, добирает остаток из любых сложностей.
    """
    count = max(1, count)
    base, remainder = divmod(count, 5)
    selected: list[QuestionItem] = []
    for difficulty in range(1, 6):
        wanted = base + (1 if difficulty <= remainder else 0)
        if wanted <= 0:
            continue
        selected.extend(
            await pick_questions(session, topic_id, difficulty=difficulty, limit=wanted)
        )

    if len(selected) < count:
        exclude = {item.id for item in selected}
        selected.extend(
            await pick_questions(
                session,
                topic_id,
                difficulty=None,
                limit=count - len(selected),
                exclude_ids=exclude,
            )
        )

    selected.sort(key=lambda item: (item.difficulty, item.id))
    return tuple(selected[:count])


MAX_TEST_ATTEMPTS = 2


class TestAlreadyCompleted(ValueError):
    """Лимит попыток по теме исчерпан."""


async def count_test_attempts(
    session: AsyncSession,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> int:
    """Сколько попыток теста уже было по теме."""
    return (
        await session.scalar(
            select(func.count())
            .select_from(TopicTestResult)
            .where(
                TopicTestResult.user_id == user_id,
                TopicTestResult.topic_id == topic_id,
            )
        )
    ) or 0


async def get_test_results(
    session: AsyncSession,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> list[TopicTestResult]:
    """Все попытки по теме, от первой к последней."""
    return list(
        (
            await session.scalars(
                select(TopicTestResult)
                .where(
                    TopicTestResult.user_id == user_id,
                    TopicTestResult.topic_id == topic_id,
                )
                .order_by(TopicTestResult.attempt_no, TopicTestResult.completed_at)
            )
        ).all()
    )


async def get_test_result(
    session: AsyncSession,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> TopicTestResult | None:
    """Лучший результат теста по теме."""
    return await session.scalar(
        select(TopicTestResult)
        .where(
            TopicTestResult.user_id == user_id,
            TopicTestResult.topic_id == topic_id,
        )
        .order_by(
            TopicTestResult.score.desc(),
            TopicTestResult.level.desc(),
            TopicTestResult.completed_at.desc(),
        )
        .limit(1)
    )


async def save_test_result(
    session: AsyncSession,
    user_id: uuid.UUID,
    topic: Topic,
    *,
    score: float,
    level: int,
    correct_count: int,
    total: int,
    details: list[dict[str, Any]],
) -> TopicTestResult:
    """Сохраняет попытку и обновляет профиль лучшим результатом."""
    attempts = await count_test_attempts(session, user_id, topic.id)
    if attempts >= MAX_TEST_ATTEMPTS:
        raise TestAlreadyCompleted("Лимит попыток по этой теме исчерпан")

    result = TopicTestResult(
        user_id=user_id,
        topic_id=topic.id,
        attempt_no=attempts + 1,
        score=score,
        level=level,
        correct_count=correct_count,
        total=total,
        details=details,
    )
    session.add(result)

    state = await session.scalar(
        select(UserSkillState).where(
            UserSkillState.user_id == user_id,
            UserSkillState.topic_id == topic.id,
        )
    )
    if state is None:
        state = UserSkillState(user_id=user_id, topic_id=topic.id)
        session.add(state)
        state.proficiency = level
        state.confidence = round(min(0.95, 0.5 + 0.45 * score), 3)
        state.source = "test"
        state.evidence_type = "test"
        state.verified_level = level
    else:
        # Новая попытка не должна ухудшать подтверждённый уровень.
        best_level = max(state.verified_level or 0, level)
        if best_level > (state.verified_level or 0):
            state.verified_level = best_level
        if level > state.proficiency:
            state.proficiency = level
            state.confidence = round(min(0.95, 0.5 + 0.45 * score), 3)
            state.source = "test"
            state.evidence_type = "test"

    state.review_due_at, state.review_interval_days = next_review(
        state.verified_level or level, state.review_interval_days
    )
    state.last_assessed = datetime.now(UTC)
    state.evidence = [
        *(state.evidence or []),
        {
            "type": "test",
            "text": f"Тест по теме: {correct_count} из {total} верно",
            "score": level,
            "attempt": attempts + 1,
        },
    ][-10:]

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise TestAlreadyCompleted("Не удалось сохранить попытку теста") from exc
    return result

