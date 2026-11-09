"""Тренировочное интервью: сценарий из плана, ответы и разбор."""

import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import ChatMessage, LLMError, LLMProvider
from app.models import (
    InterviewSession,
    InterviewTurn,
    LearningPlan,
    PlanItem,
    Question,
    Topic,
    UserSkillState,
)
from app.questions.generator import generate_questions
from app.services.profile import weighted_estimate
from app.services.questions import add_questions, pick_questions

MAX_INTERVIEW_QUESTIONS = 8
EVALUATION_SCHEMA_NAME = "interview_evaluation"

EVALUATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["score", "verdict", "covered_points", "missed_points", "feedback_brief"],
    "properties": {
        "score": {"type": "number", "minimum": 0, "maximum": 100},
        "verdict": {"type": "string", "enum": ["strong", "partial", "weak"]},
        "covered_points": {"type": "array", "items": {"type": "string"}},
        "missed_points": {"type": "array", "items": {"type": "string"}},
        "feedback_brief": {"type": "string"},
    },
}

EVALUATION_SYSTEM_PROMPT = (
    "Ты — технический интервьюер. Оцени ответ кандидата по вопросу и эталонным пунктам.\n"
    "Правила:\n"
    "- score 0..100: насколько ответ полный и корректный.\n"
    "- verdict: strong / partial / weak.\n"
    "- covered_points: что кандидат действительно объяснил.\n"
    "- missed_points: важные пункты, которых не хватило.\n"
    "- feedback_brief: 2–4 предложения, что верно и что подтянуть.\n"
    "- Не придумывай факты, которых нет в ответе."
)

FEEDBACK_STREAM_PROMPT = (
    "Ты — технический интервьюер. Напиши короткий живой фидбек кандидату: "
    "2–4 предложения. Скажи, что получилось, что упущено и что подтянуть. "
    "Не меняй выставленную оценку и не задавай новый вопрос."
)


class InterviewError(ValueError):
    """Интервью нельзя создать или продолжить."""


class InterviewNotFound(LookupError):
    """Интервью не найдено у пользователя."""


class InterviewStateError(ValueError):
    """Действие не соответствует состоянию интервью."""


@dataclass(frozen=True)
class InterviewTurnData:
    """Вопрос интервью и результат ответа."""

    id: uuid.UUID
    position: int
    topic_id: uuid.UUID
    topic_key: str
    topic_name: str
    question_id: uuid.UUID | None
    question_text: str
    difficulty: int
    status: str
    answer_text: str | None
    score: float | None
    verdict: str | None
    feedback: str | None
    covered_points: tuple[str, ...]
    missed_points: tuple[str, ...]
    answered_at: datetime | None


@dataclass(frozen=True)
class InterviewSnapshot:
    """Сессия интервью целиком."""

    id: uuid.UUID
    user_id: uuid.UUID
    plan_id: uuid.UUID | None
    title: str
    status: str
    score: float | None
    level: int | None
    question_count: int
    answered_count: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    turns: tuple[InterviewTurnData, ...]


@dataclass(frozen=True)
class AnswerOutcome:
    """Результат ответа: оценка, следующий вопрос и финал."""

    turn: InterviewTurnData
    next_turn: InterviewTurnData | None
    session: InterviewSnapshot
    finished: bool


@dataclass(frozen=True)
class InterviewSummary:
    """Краткая карточка интервью."""

    id: uuid.UUID
    title: str
    status: str
    level: int | None
    question_count: int
    answered_count: int
    created_at: datetime


async def create_interview(
    session: AsyncSession,
    user_id: uuid.UUID,
    plan_id: uuid.UUID,
    *,
    provider: LLMProvider | None = None,
) -> InterviewSnapshot:
    """Создаёт сценарий интервью из тем плана.

    Темы без вопросов добираются ленивой генерацией, чтобы интервью не
    обрывалось на двух вопросах из-за неполного банка.
    """
    plan = await session.get(LearningPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise InterviewNotFound("План не найден")

    rows = (
        await session.execute(
            select(PlanItem, Topic)
            .join(Topic, Topic.id == PlanItem.topic_id)
            .where(PlanItem.plan_id == plan.id)
            .order_by(PlanItem.position)
        )
    ).all()
    if not rows:
        raise InterviewError("В плане нет тем")

    selected: list[tuple[PlanItem, Topic, Question]] = []
    for item, topic in rows:
        if len(selected) >= MAX_INTERVIEW_QUESTIONS:
            break
        difficulty = _difficulty_for(item.current_level, item.target_level)
        question = await _pick_or_generate_question(
            session, topic, difficulty, provider
        )
        if question is not None:
            selected.append((item, topic, question))

    if not selected:
        raise InterviewError("В банке нет вопросов для тем плана")

    interview = InterviewSession(
        user_id=user_id,
        plan_id=plan.id,
        title=plan.title,
        status="in_progress",
        question_count=len(selected),
        started_at=datetime.now(UTC),
    )
    session.add(interview)
    await session.flush()

    for position, (_, _, question) in enumerate(selected, start=1):
        session.add(
            InterviewTurn(
                session_id=interview.id,
                topic_id=question.topic_id,
                question_id=question.id,
                position=position,
                question_text=question.text,
                expected_points=list(question.expected_points or []),
                difficulty=question.difficulty,
                status="pending",
            )
        )
    await session.commit()
    return await get_interview(session, user_id, interview.id)


async def get_interview(
    session: AsyncSession,
    user_id: uuid.UUID,
    interview_id: uuid.UUID,
) -> InterviewSnapshot:
    """Возвращает сессию с вопросами или 404."""
    interview = await session.get(InterviewSession, interview_id)
    if interview is None or interview.user_id != user_id:
        raise InterviewNotFound("Интервью не найдено")

    rows = (
        await session.execute(
            select(InterviewTurn, Topic)
            .join(Topic, Topic.id == InterviewTurn.topic_id)
            .where(InterviewTurn.session_id == interview.id)
            .order_by(InterviewTurn.position)
        )
    ).all()
    turns = tuple(_turn_data(turn, topic) for turn, topic in rows)
    return _snapshot(interview, turns)


async def list_interviews(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[InterviewSummary]:
    """Список интервью пользователя, новые сверху."""
    interviews = (
        await session.scalars(
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.desc())
        )
    ).all()
    result: list[InterviewSummary] = []
    for interview in interviews:
        answered = (
            await session.scalar(
                select(func.count())
                .select_from(InterviewTurn)
                .where(
                    InterviewTurn.session_id == interview.id,
                    InterviewTurn.status == "answered",
                )
            )
        ) or 0
        result.append(
            InterviewSummary(
                id=interview.id,
                title=interview.title,
                status=interview.status,
                level=interview.level,
                question_count=interview.question_count,
                answered_count=answered,
                created_at=interview.created_at,
            )
        )
    return result


async def answer_turn(
    session: AsyncSession,
    user_id: uuid.UUID,
    interview_id: uuid.UUID,
    turn_id: uuid.UUID,
    answer_text: str,
    provider: LLMProvider,
) -> AnswerOutcome:
    """Оценивает ответ и возвращает следующий вопрос или финал."""
    interview = await session.get(InterviewSession, interview_id)
    if interview is None or interview.user_id != user_id:
        raise InterviewNotFound("Интервью не найдено")
    if interview.status != "in_progress":
        raise InterviewStateError("Интервью уже завершено")

    turn = await session.get(InterviewTurn, turn_id)
    if turn is None or turn.session_id != interview.id:
        raise InterviewNotFound("Вопрос интервью не найден")
    if turn.status != "pending":
        raise InterviewStateError("На этот вопрос уже дан ответ")

    pending_position = await session.scalar(
        select(func.min(InterviewTurn.position)).where(
            InterviewTurn.session_id == interview.id,
            InterviewTurn.status == "pending",
        )
    )
    if pending_position is not None and turn.position != pending_position:
        raise InterviewStateError("Сначала ответьте на текущий вопрос")

    text = answer_text.strip()
    if len(text) < 3:
        raise InterviewError("Ответ слишком короткий")

    evaluation = await _evaluate_answer(provider, turn, text)
    turn.answer_text = text
    turn.score = evaluation["score"]
    turn.verdict = evaluation["verdict"]
    turn.feedback = evaluation["feedback_brief"]
    turn.covered_points = evaluation["covered_points"]
    turn.missed_points = evaluation["missed_points"]
    turn.status = "answered"
    turn.answered_at = datetime.now(UTC)
    await session.flush()

    next_turn = await session.scalar(
        select(InterviewTurn)
        .where(
            InterviewTurn.session_id == interview.id,
            InterviewTurn.status == "pending",
        )
        .order_by(InterviewTurn.position)
        .limit(1)
    )
    finished = next_turn is None
    if finished:
        await _finish(session, interview)
    await session.commit()

    updated = await get_interview(session, user_id, interview.id)
    return AnswerOutcome(
        turn=_find_turn(updated, turn.id),
        next_turn=_find_turn(updated, next_turn.id) if next_turn is not None else None,
        session=updated,
        finished=finished,
    )


async def stream_feedback(
    provider: LLMProvider,
    turn: InterviewTurnData,
    answer_text: str,
) -> AsyncIterator[str]:
    """Стримит живой фидбек по уже выставленной оценке."""
    messages = [
        ChatMessage("system", FEEDBACK_STREAM_PROMPT),
        ChatMessage(
            "user",
            (
                f"Вопрос: {turn.question_text}\n"
                f"Ответ кандидата: {answer_text}\n"
                f"Оценка: {turn.score}/100 ({turn.verdict})\n"
                f"Верно: {'; '.join(turn.covered_points) or '—'}\n"
                f"Упущено: {'; '.join(turn.missed_points) or '—'}"
            ),
        ),
    ]
    try:
        async for chunk in provider.generate_stream(messages):
            yield chunk
    except LLMError:
        return


async def _evaluate_answer(
    provider: LLMProvider,
    turn: InterviewTurn,
    answer_text: str,
) -> dict[str, Any]:
    """Один структурированный вызов оценки ответа."""
    messages = [
        ChatMessage("system", EVALUATION_SYSTEM_PROMPT),
        ChatMessage(
            "user",
            (
                f"Вопрос: {turn.question_text}\n"
                f"Сложность: {turn.difficulty}/5\n"
                f"Эталонные пункты: {'; '.join(str(item) for item in turn.expected_points or []) or '—'}\n"
                f"Ответ кандидата: {answer_text}"
            ),
        ),
    ]
    result = await provider.generate_structured(
        messages, EVALUATION_SCHEMA, schema_name=EVALUATION_SCHEMA_NAME
    )
    data = result.data
    score = _clamp_score(data.get("score"))
    verdict = str(data.get("verdict") or "weak")
    if verdict not in ("strong", "partial", "weak"):
        verdict = "partial"
    return {
        "score": score,
        "verdict": verdict,
        "covered_points": _clean_points(data.get("covered_points")),
        "missed_points": _clean_points(data.get("missed_points")),
        "feedback_brief": _clean_text(data.get("feedback_brief"), 1000),
    }


async def _finish(session: AsyncSession, interview: InterviewSession) -> None:
    """Считает итог и обновляет профиль по темам."""
    turns = (
        await session.scalars(
            select(InterviewTurn).where(
                InterviewTurn.session_id == interview.id,
                InterviewTurn.status == "answered",
            )
        )
    ).all()
    weighted = sum((turn.score or 0) * turn.difficulty for turn in turns)
    total = sum(turn.difficulty for turn in turns)
    score = weighted / total if total else 0.0
    interview.score = round(score, 3)
    interview.level = round(score)
    interview.status = "completed"
    interview.finished_at = datetime.now(UTC)

    by_topic: dict[uuid.UUID, list[tuple[float, int]]] = {}
    for turn in turns:
        by_topic.setdefault(turn.topic_id, []).append((turn.score or 0, turn.difficulty))

    for topic_id, values in by_topic.items():
        topic_score = sum(value * difficulty for value, difficulty in values) / sum(
            difficulty for _, difficulty in values
        )
        state = await session.scalar(
            select(UserSkillState).where(
                UserSkillState.user_id == interview.user_id,
                UserSkillState.topic_id == topic_id,
            )
        )
        if state is None:
            state = UserSkillState(user_id=interview.user_id, topic_id=topic_id)
            session.add(state)
            level, confidence = round(topic_score), 0.9
        else:
            level, confidence = weighted_estimate(
                [(state.proficiency, state.confidence), (round(topic_score), 0.9)]
            )
        state.proficiency = level
        state.confidence = confidence
        state.source = "interview"
        state.last_assessed = datetime.now(UTC)
        state.evidence = [
            *(state.evidence or []),
            {
                "type": "interview",
                "text": f"Интервью: {round(topic_score)} из 100",
                "score": round(topic_score),
            },
        ][-10:]


def _snapshot(
    interview: InterviewSession,
    turns: Sequence[InterviewTurnData],
) -> InterviewSnapshot:
    """Собирает доменный снимок сессии."""
    return InterviewSnapshot(
        id=interview.id,
        user_id=interview.user_id,
        plan_id=interview.plan_id,
        title=interview.title,
        status=interview.status,
        score=interview.score,
        level=interview.level,
        question_count=interview.question_count,
        answered_count=sum(1 for turn in turns if turn.status == "answered"),
        created_at=interview.created_at,
        started_at=interview.started_at,
        finished_at=interview.finished_at,
        turns=tuple(turns),
    )


def _turn_data(turn: InterviewTurn, topic: Topic) -> InterviewTurnData:
    """Преобразует ORM-ход в доменный объект."""
    return InterviewTurnData(
        id=turn.id,
        position=turn.position,
        topic_id=topic.id,
        topic_key=topic.key,
        topic_name=topic.name,
        question_id=turn.question_id,
        question_text=turn.question_text,
        difficulty=turn.difficulty,
        status=turn.status,
        answer_text=turn.answer_text,
        score=turn.score,
        verdict=turn.verdict,
        feedback=turn.feedback,
        covered_points=tuple(str(item) for item in turn.covered_points or []),
        missed_points=tuple(str(item) for item in turn.missed_points or []),
        answered_at=turn.answered_at,
    )


def _find_turn(snapshot: InterviewSnapshot, turn_id: uuid.UUID) -> InterviewTurnData:
    """Находит ход в снимке."""
    for turn in snapshot.turns:
        if turn.id == turn_id:
            return turn
    raise InterviewNotFound("Вопрос интервью не найден")


async def _pick_or_generate_question(
    session: AsyncSession,
    topic: Topic,
    difficulty: int,
    provider: LLMProvider | None,
) -> Question | None:
    """Берёт вопрос из банка или генерирует его для темы плана."""
    questions = await pick_questions(session, topic.id, difficulty=difficulty, limit=1)
    if not questions:
        questions = await pick_questions(session, topic.id, difficulty=None, limit=1)
    if questions:
        return await session.get(Question, questions[0].id)

    if provider is None:
        return None
    try:
        generated = await generate_questions(provider, topic, difficulty, 3)
    except LLMError:
        return None
    if not generated:
        return None
    await add_questions(session, topic.id, difficulty, generated)
    await session.flush()
    questions = await pick_questions(session, topic.id, difficulty=difficulty, limit=1)
    if not questions:
        questions = await pick_questions(session, topic.id, difficulty=None, limit=1)
    if not questions:
        return None
    return await session.get(Question, questions[0].id)


def _difficulty_for(current: int, target: int) -> int:
    """Подбирает сложность по разрыву между текущим и целевым уровнем."""
    gap = max(0, target - current)
    if gap >= 30:
        return 2
    if gap >= 10:
        return 3
    return 4


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(100.0, score)), 1)


def _clean_points(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:8]


def _clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]
