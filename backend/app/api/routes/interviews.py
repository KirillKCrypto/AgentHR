"""Эндпоинты тренировочного интервью."""

import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession, LlmProvider
from app.api.mappers import interview_read, interview_summary_read, interview_turn_read
from app.models import InterviewTurn
from app.schemas.interview import (
    InterviewAnswerRead,
    InterviewAnswerRequest,
    InterviewCreate,
    InterviewRead,
    InterviewSummaryRead,
)
from app.services.interview import (
    InterviewError,
    InterviewNotFound,
    InterviewStateError,
    answer_turn,
    create_interview,
    get_interview,
    list_interviews,
    stream_feedback,
)

router = APIRouter(prefix="/interviews", tags=["interviews"])


def _raise(exc: Exception) -> None:
    if isinstance(exc, InterviewNotFound):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, InterviewStateError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
    ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_interview(
    payload: InterviewCreate,
    db: DbSession,
    provider: LlmProvider,
    current_user: CurrentUser,
) -> InterviewRead:
    """Создаёт интервью из последнего плана подготовки."""
    try:
        snapshot = await create_interview(
            db,
            current_user.id,
            plan_id=payload.plan_id,
            vacancy_id=payload.vacancy_id,
            provider=provider,
        )
    except (InterviewError, InterviewNotFound, InterviewStateError) as exc:
        _raise(exc)
        raise
    return interview_read(snapshot)


@router.get("")
async def read_interviews(
    db: DbSession,
    current_user: CurrentUser,
) -> list[InterviewSummaryRead]:
    """Список интервью пользователя."""
    return [
        interview_summary_read(item)
        for item in await list_interviews(db, current_user.id)
    ]


@router.get("/{interview_id}")
async def read_interview(
    interview_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> InterviewRead:
    """Сессия интервью с вопросами и разбором."""
    try:
        snapshot = await get_interview(db, current_user.id, interview_id)
    except InterviewNotFound as exc:
        _raise(exc)
        raise
    return interview_read(snapshot)


@router.post("/{interview_id}/answers")
async def answer(
    interview_id: UUID,
    payload: InterviewAnswerRequest,
    db: DbSession,
    provider: LlmProvider,
    current_user: CurrentUser,
) -> InterviewAnswerRead:
    """Оценивает ответ и возвращает следующий вопрос."""
    try:
        outcome = await answer_turn(
            db,
            current_user.id,
            interview_id,
            payload.turn_id,
            payload.answer_text,
            provider,
        )
    except (InterviewError, InterviewNotFound, InterviewStateError) as exc:
        _raise(exc)
        raise
    return InterviewAnswerRead(
        turn=interview_turn_read(outcome.turn),
        next_turn=interview_turn_read(outcome.next_turn) if outcome.next_turn else None,
        session=interview_read(outcome.session),
        finished=outcome.finished,
    )


@router.post("/{interview_id}/answers/stream")
async def answer_stream(
    interview_id: UUID,
    payload: InterviewAnswerRequest,
    db: DbSession,
    provider: LlmProvider,
    current_user: CurrentUser,
    request: Request,
) -> StreamingResponse:
    """Оценивает ответ и стримит фидбек через SSE."""
    try:
        outcome = await answer_turn(
            db,
            current_user.id,
            interview_id,
            payload.turn_id,
            payload.answer_text,
            provider,
        )
    except (InterviewError, InterviewNotFound, InterviewStateError) as exc:
        _raise(exc)
        raise

    async def events() -> AsyncIterator[str]:
        yield _sse(
            "evaluation",
            {
                "turn": interview_turn_read(outcome.turn).model_dump(mode="json"),
                "finished": outcome.finished,
            },
        )
        chunks: list[str] = []
        try:
            async for chunk in stream_feedback(provider, outcome.turn, payload.answer_text):
                if await request.is_disconnected():
                    break
                chunks.append(chunk)
                yield _sse("token", {"text": chunk})
        finally:
            if chunks:
                turn = await db.get(InterviewTurn, outcome.turn.id)
                if turn is not None:
                    turn.feedback = "".join(chunks)
                    await db.commit()
        yield _sse(
            "done",
            {
                "feedback": "".join(chunks) or outcome.turn.feedback,
                "next_turn": (
                    interview_turn_read(outcome.next_turn).model_dump(mode="json")
                    if outcome.next_turn
                    else None
                ),
                "session": interview_read(outcome.session).model_dump(mode="json"),
                "finished": outcome.finished,
            },
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict) -> str:
    """Формирует один SSE-кадр с JSON в data."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
