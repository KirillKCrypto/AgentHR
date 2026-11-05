"""Эндпоинт банка вопросов."""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Topic
from app.schemas.plan import QuestionRead
from app.services.questions import pick_questions

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("")
async def read_questions(
    db: DbSession,
    current_user: CurrentUser,
    topic_key: str = Query(min_length=1, max_length=64),
    difficulty: int | None = Query(default=None, ge=1, le=5),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[QuestionRead]:
    """Случайные вопросы по теме онтологии."""
    topic = await db.scalar(select(Topic).where(Topic.key == topic_key))
    if topic is None or topic.status not in ("canonical", "provisional"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тема не найдена")

    questions = await pick_questions(
        db,
        topic.id,
        difficulty=difficulty,
        limit=limit,
    )
    return [
        QuestionRead(
            id=item.id,
            topic_id=item.topic_id,
            difficulty=item.difficulty,
            text=item.text,
            expected_points=list(item.expected_points),
            source=item.source,
        )
        for item in questions
    ]
