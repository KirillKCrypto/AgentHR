"""Эндпоинты банка вопросов и тестов по темам."""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, LlmProvider
from app.models import Question, Topic
from app.questions.quiz import QuizError, ensure_quiz_options
from app.schemas.plan import QuestionRead
from app.schemas.quiz import (
    QuizGradeRequest,
    QuizQuestionRead,
    QuizRead,
    QuizResultItemRead,
    QuizResultRead,
    QuizStartRequest,
)
from app.services.questions import (
    TestAlreadyCompleted,
    get_test_result,
    pick_questions,
    pick_test_questions,
    save_test_result,
)

router = APIRouter(prefix="/questions", tags=["questions"])


async def _load_topic(db: AsyncSession, topic_key: str) -> Topic:
    """Тема по ключу или 404."""
    topic = await db.scalar(select(Topic).where(Topic.key == topic_key))
    if topic is None or topic.status not in ("canonical", "provisional"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тема не найдена")
    return topic


@router.post("/quiz", status_code=status.HTTP_201_CREATED)
async def start_quiz(
    payload: QuizStartRequest,
    db: DbSession,
    provider: LlmProvider,
    current_user: CurrentUser,
) -> QuizRead:
    """Собирает тест по теме и при необходимости готовит варианты ответа."""
    topic = await _load_topic(db, payload.topic_key)
    if await get_test_result(db, current_user.id, topic.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Тест по этой теме уже пройден",
        )
    picked = await pick_test_questions(db, topic.id, count=payload.count)
    if not picked:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Для темы пока нет вопросов",
        )

    ids = [item.id for item in picked]
    questions = {
        question.id: question
        for question in (
            await db.scalars(select(Question).where(Question.id.in_(ids)))
        ).all()
    }
    ordered = [questions[item.id] for item in picked if item.id in questions]
    try:
        await ensure_quiz_options(db, provider, ordered)
    except QuizError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    await db.commit()

    return QuizRead(
        topic_key=topic.key,
        topic_name=topic.name,
        questions=[
            QuizQuestionRead(
                id=question.id,
                difficulty=question.difficulty,
                text=question.text,
                options=[str(option) for option in question.options or []],
            )
            for question in ordered
        ],
    )


@router.post("/quiz/grade")
async def grade_quiz(
    payload: QuizGradeRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> QuizResultRead:
    """Проверяет ответы и возвращает разбор с метрикой по теме."""
    topic = await _load_topic(db, payload.topic_key)
    ids = [answer.question_id for answer in payload.answers]
    questions = {
        question.id: question
        for question in (
            await db.scalars(
                select(Question).where(
                    Question.id.in_(ids),
                    Question.topic_id == topic.id,
                )
            )
        ).all()
    }

    items: list[QuizResultItemRead] = []
    earned = 0
    total = 0
    for answer in payload.answers:
        question = questions.get(answer.question_id)
        if question is None or question.correct_option is None or not question.options:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Вопрос теста не найден или не подготовлен",
            )
        correct = answer.selected_option == question.correct_option
        total += question.difficulty
        if correct:
            earned += question.difficulty
        items.append(
            QuizResultItemRead(
                question_id=question.id,
                text=question.text,
                difficulty=question.difficulty,
                options=[str(option) for option in question.options],
                selected_option=answer.selected_option,
                correct_option=question.correct_option,
                is_correct=correct,
                explanation=question.explanation,
                expected_points=[str(item) for item in question.expected_points or []],
            )
        )

    score = earned / total if total > 0 else 0.0
    result = QuizResultRead(
        topic_key=topic.key,
        topic_name=topic.name,
        score=round(score, 3),
        level=round(score * 100),
        correct_count=sum(1 for item in items if item.is_correct),
        total=len(items),
        items=items,
    )
    try:
        await save_test_result(
            db,
            current_user.id,
            topic,
            score=result.score,
            level=result.level,
            correct_count=result.correct_count,
            total=result.total,
            details=[item.model_dump(mode="json") for item in items],
        )
    except TestAlreadyCompleted as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    await db.commit()
    return result


@router.get("/quiz/{topic_key}/result")
async def read_test_result(
    topic_key: str,
    db: DbSession,
    current_user: CurrentUser,
) -> QuizResultRead:
    """Сохранённый результат теста по теме."""
    topic = await _load_topic(db, topic_key)
    saved = await get_test_result(db, current_user.id, topic.id)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тест по этой теме ещё не пройден",
        )
    return QuizResultRead(
        topic_key=topic.key,
        topic_name=topic.name,
        score=saved.score,
        level=saved.level,
        correct_count=saved.correct_count,
        total=saved.total,
        items=[QuizResultItemRead(**item) for item in saved.details or []],
    )


@router.get("/test")
async def read_test(
    db: DbSession,
    current_user: CurrentUser,
    topic_key: str = Query(min_length=1, max_length=64),
    count: int = Query(default=10, ge=5, le=20),
) -> list[QuestionRead]:
    """Открытые вопросы разной сложности без вариантов ответа."""
    topic = await _load_topic(db, topic_key)
    questions = await pick_test_questions(db, topic.id, count=count)
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


@router.get("")
async def read_questions(
    db: DbSession,
    current_user: CurrentUser,
    topic_key: str = Query(min_length=1, max_length=64),
    difficulty: int | None = Query(default=None, ge=1, le=5),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[QuestionRead]:
    """Случайные вопросы по теме онтологии."""
    topic = await _load_topic(db, topic_key)
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
