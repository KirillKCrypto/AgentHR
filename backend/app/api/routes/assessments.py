"""API мини-тестов навыков."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models import Topic
from app.schemas.assessment import (
    AssessmentAnswerRead,
    AssessmentAnswerRequest,
    AssessmentFinishRead,
    AssessmentOption,
    AssessmentQuestionRead,
    AssessmentResultItem,
    AssessmentStartRead,
    AssessmentTopicRead,
)
from app.services.assessment import (
    AssessmentNotFound,
    AssessmentStateError,
    AssessmentValidationError,
    answer_question,
    finish_assessment,
    list_available_topics,
    start_assessment,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.get("/topics")
async def read_assessment_topics(
    db: DbSession,
    current_user: CurrentUser,
) -> list[AssessmentTopicRead]:
    """Темы, для которых доступны мини-тесты."""
    rows = await list_available_topics(db, current_user.id)
    return [AssessmentTopicRead(**row) for row in rows]


@router.post("/{topic_key}/start")
async def start_topic_assessment(
    topic_key: str,
    db: DbSession,
    current_user: CurrentUser,
) -> AssessmentStartRead:
    """Стартует тест или возвращает активную попытку."""
    try:
        attempt, questions = await start_assessment(db, current_user.id, topic_key)
    except AssessmentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssessmentStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    topic = await db.get(Topic, attempt.topic_id)
    return AssessmentStartRead(
        attempt_id=attempt.id,
        topic_key=topic.key if topic is not None else topic_key,
        topic_name=topic.name if topic is not None else topic_key,
        questions=[
            AssessmentQuestionRead(
                id=question.id,
                difficulty=question.difficulty,
                kind=question.kind,
                prompt=question.prompt,
                options=[AssessmentOption(**option) for option in question.options],
            )
            for question in questions
        ],
    )


@router.post("/{attempt_id}/answers")
async def answer_assessment_question(
    attempt_id: UUID,
    payload: AssessmentAnswerRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> AssessmentAnswerRead:
    """Принимает ответ на вопрос."""
    try:
        answered, total = await answer_question(
            db,
            current_user.id,
            attempt_id,
            payload.question_id,
            payload.answer_key,
        )
    except AssessmentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssessmentStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AssessmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AssessmentAnswerRead(
        question_id=payload.question_id,
        answered_count=answered,
        total=total,
    )


@router.post("/{attempt_id}/finish")
async def finish_attempt(
    attempt_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> AssessmentFinishRead:
    """Завершает тест и возвращает разбор."""
    try:
        result = await finish_assessment(db, current_user.id, attempt_id)
    except AssessmentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssessmentStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    attempt = result["attempt"]
    return AssessmentFinishRead(
        attempt_id=attempt.id,
        topic_key=result["topic_key"],
        topic_name=result["topic_name"],
        test_level=attempt.test_level or 0,
        confidence=attempt.confidence,
        score=attempt.score or 0.0,
        correct_count=result["correct_count"],
        total=result["total"],
        items=[AssessmentResultItem(**item) for item in result["items"]],
    )
