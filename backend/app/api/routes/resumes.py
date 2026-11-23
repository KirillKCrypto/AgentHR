"""Эндпоинты резюме: загрузка, история, активное резюме и удаление."""

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, Embedder, LlmProvider
from app.api.mappers import resume_read
from app.models import Resume, ResumeSkill
from app.schemas.analysis import ResumeCreate, ResumeRead, ResumeSummary
from app.services.analysis import AnalysisError
from app.services.documents import MAX_UPLOAD_BYTES, DocumentError, extract_resume_text
from app.services.profile import (
    NotFoundError,
    activate_resume,
    analyze_resume,
    clear_resumes,
    delete_resume,
    find_resume_by_text,
    get_resume,
    load_resume_skills,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_resume(
    payload: ResumeCreate,
    response: Response,
    db: DbSession,
    provider: LlmProvider,
    embedder: Embedder,
    current_user: CurrentUser,
) -> ResumeRead:
    """Создаёт резюме, извлекает навыки и делает его активным."""
    existing = await find_resume_by_text(db, current_user.id, payload.raw_text)
    if existing is not None:
        resume = await activate_resume(
            db, current_user.id, existing.id, title=payload.title
        )
        response.status_code = status.HTTP_200_OK
        skills = await load_resume_skills(db, resume.id)
        return resume_read(resume, skills, reused=True)

    try:
        resume = await analyze_resume(
            db,
            provider,
            current_user.id,
            raw_text=payload.raw_text,
            title=payload.title,
            embedder=embedder,
        )
    except AnalysisError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    skills = await load_resume_skills(db, resume.id)
    return resume_read(resume, skills)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_resume(
    response: Response,
    db: DbSession,
    provider: LlmProvider,
    embedder: Embedder,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
) -> ResumeRead:
    """Загружает PDF/DOCX, извлекает текст и сохраняет резюме.

    Повторная загрузка того же текста возвращает существующее резюме.
    """
    content = await _read_limited(file)
    await file.close()
    try:
        raw_text = await asyncio.to_thread(extract_resume_text, file.filename, content)
    except DocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    clean_title = (title or "").strip() or None
    existing = await find_resume_by_text(db, current_user.id, raw_text)
    if existing is not None:
        resume = await activate_resume(
            db, current_user.id, existing.id, title=clean_title
        )
        response.status_code = status.HTTP_200_OK
        skills = await load_resume_skills(db, resume.id)
        return resume_read(resume, skills, reused=True)

    try:
        resume = await analyze_resume(
            db,
            provider,
            current_user.id,
            raw_text=raw_text,
            title=clean_title,
            embedder=embedder,
        )
    except AnalysisError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    skills = await load_resume_skills(db, resume.id)
    return resume_read(resume, skills)


async def _read_limited(file: UploadFile) -> bytes:
    """Читает файл, не превышая лимит размера."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Файл больше {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("")
async def list_resumes(
    db: DbSession,
    current_user: CurrentUser,
) -> list[ResumeSummary]:
    """История резюме пользователя с числом навыков."""
    rows = (
        await db.execute(
            select(Resume, func.count(ResumeSkill.id))
            .outerjoin(ResumeSkill, ResumeSkill.resume_id == Resume.id)
            .where(Resume.user_id == current_user.id)
            .group_by(Resume.id)
            .order_by(Resume.created_at.desc())
        )
    ).all()
    return [
        ResumeSummary(
            id=resume.id,
            title=resume.title,
            created_at=resume.created_at,
            skills_count=int(skills_count or 0),
            is_active=resume.is_active,
        )
        for resume, skills_count in rows
    ]


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_resume_history(
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Удаляет все резюме; оценки из интервью и ручные оценки сохраняются."""
    await clear_resumes(db, current_user.id)


@router.get("/{resume_id}")
async def read_resume(
    resume_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ResumeRead:
    """Возвращает резюме с текстом и навыками."""
    try:
        resume = await get_resume(db, current_user.id, resume_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    skills = await load_resume_skills(db, resume.id)
    return resume_read(resume, skills)


@router.post("/{resume_id}/activate")
async def make_resume_active(
    resume_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ResumeRead:
    """Делает резюме активным и пересобирает профиль."""
    try:
        resume = await activate_resume(db, current_user.id, resume_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    skills = await load_resume_skills(db, resume.id)
    return resume_read(resume, skills)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_resume(
    resume_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Удаляет резюме; активным становится следующее по дате."""
    try:
        await delete_resume(db, current_user.id, resume_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
