"""Прокси голосового ввода в STT-сервис GigaAM."""

from typing import Annotated
from uuid import UUID

import httpx2
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.models import InterviewSession, InterviewTurn
from app.schemas.interview import TranscriptionRead

router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])
MAX_AUDIO_BYTES = 25 * 1024 * 1024


@router.post("")
async def transcribe_audio(
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
    interview_id: Annotated[UUID, Form()],
    turn_id: Annotated[UUID, Form()],
) -> TranscriptionRead:
    """Проверяет доступ и пересылает аудио в GigaAM."""
    settings = get_settings()
    if not settings.stt_base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Голосовой ввод не настроен",
        )
    interview = await db.get(InterviewSession, interview_id)
    if interview is None or interview.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Интервью не найдено")
    turn = await db.get(InterviewTurn, turn_id)
    if turn is None or turn.session_id != interview.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вопрос не найден")
    if turn.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Вопрос уже отвечен")

    payload = await file.read()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Пустой аудиофайл",
        )
    if len(payload) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Аудио слишком большое",
        )

    try:
        async with httpx2.AsyncClient(timeout=settings.stt_timeout_seconds) as client:
            response = await client.post(
                f"{settings.stt_base_url.rstrip('/')}/transcribe",
                files={
                    "file": (
                        file.filename or "answer.webm",
                        payload,
                        file.content_type or "audio/webm",
                    )
                },
            )
    except httpx2.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Сервис распознавания недоступен",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось распознать аудио",
        )
    data = response.json()
    return TranscriptionRead(
        text=str(data.get("text") or ""),
        duration_ms=data.get("duration_ms"),
        confidence=data.get("confidence"),
    )
