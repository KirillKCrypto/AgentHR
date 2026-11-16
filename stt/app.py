"""STT-сервис GigaAM: приём аудио и распознавание русской речи."""

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)
MODEL_NAME = os.getenv("GIGAAM_MODEL", "v3_e2e_ctc")
MOCK = os.getenv("GIGAAM_MOCK", "").lower() in {"1", "true", "yes"}
MAX_BYTES = 25 * 1024 * 1024
CHUNK_SECONDS = 20

app = FastAPI(title="AgentHR STT")
_model = None


class Transcription(BaseModel):
    """Результат распознавания."""

    text: str
    duration_ms: int | None = None
    confidence: float | None = None


@app.on_event("startup")
def load_model() -> None:
    """Загружает модель один раз при старте."""
    global _model
    if MOCK:
        logger.info("STT запущен в mock-режиме")
        return
    try:
        import gigaam

        _model = gigaam.load_model(MODEL_NAME)
        logger.info("GigaAM загружен: %s", MODEL_NAME)
    except Exception:
        logger.exception("Не удалось загрузить GigaAM")


@app.get("/health")
def health() -> dict[str, str]:
    """Готовность сервиса."""
    status = "ok" if MOCK or _model is not None else "loading"
    return {"status": status, "model": MODEL_NAME}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> Transcription:
    """Распознаёт аудио; длинные файлы режет на короткие сегменты."""
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=422, detail="Пустой файл")
    if len(payload) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    if MOCK:
        return Transcription(text="Это тестовая расшифровка ответа.", duration_ms=1000)

    if _model is None:
        raise HTTPException(status_code=503, detail="Модель ещё загружается")

    suffix = Path(file.filename or "answer.webm").suffix or ".webm"
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / f"answer{suffix}"
        source.write_bytes(payload)
        wav = Path(tmp) / "answer.wav"
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(source),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(wav),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.SubprocessError as exc:
            raise HTTPException(status_code=422, detail="Не удалось прочитать аудио") from exc

        duration_ms = _duration_ms(wav)
        segments = _split(wav, Path(tmp))
        texts: list[str] = []
        for segment in segments:
            result = _model.transcribe(str(segment))
            text = getattr(result, "text", result)
            texts.append(str(text).strip())
        return Transcription(
            text=" ".join(part for part in texts if part),
            duration_ms=duration_ms,
        )


def _duration_ms(path: Path) -> int | None:
    """Длительность аудио через ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        return int(float(data["format"]["duration"]) * 1000)
    except (subprocess.SubprocessError, KeyError, ValueError):
        return None


def _split(path: Path, directory: Path) -> list[Path]:
    """Режет аудио на сегменты по 20 секунд."""
    pattern = directory / "chunk_%03d.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-f",
            "segment",
            "-segment_time",
            str(CHUNK_SECONDS),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(pattern),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return sorted(directory.glob("chunk_*.wav"))
