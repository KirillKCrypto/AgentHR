"""Извлечение текста из загруженных резюме (PDF и DOCX).

Файл не сохраняется: в БД попадает только извлечённый текст. Ограничения
защищают LLM и процесс от гигантских документов и zip-бомб.
"""

import io
import zipfile
from pathlib import Path

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_EXTRACTED_CHARS = 50_000
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 40
MIN_TEXT_CHARS = 20

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


class DocumentError(ValueError):
    """Файл не удалось прочитать или он не подходит по формату."""


def extract_resume_text(filename: str | None, content: bytes) -> str:
    """Возвращает текст резюме из PDF или DOCX."""
    extension = Path(filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentError("Поддерживаются только файлы PDF и DOCX")
    if not content:
        raise DocumentError("Файл пустой")
    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentError(
            f"Файл больше {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ — загрузите текст вручную"
        )

    if extension == ".pdf":
        text = _extract_pdf(content)
    else:
        text = _extract_docx(content)

    cleaned = _clean_text(text)
    if len(cleaned) < MIN_TEXT_CHARS:
        raise DocumentError(
            "Не удалось извлечь текст: документ пустой или содержит только изображения. "
            "Загрузите текст вручную."
        )
    return cleaned[:MAX_EXTRACTED_CHARS]


def _extract_pdf(content: bytes) -> str:
    """Извлекает текстовый слой PDF; сканы без текста дают пустую строку."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise DocumentError("PDF защищён паролем — загрузите текст вручную") from exc
        pages = reader.pages[:MAX_PDF_PAGES]
        return "\n".join(page.extract_text() or "" for page in pages)
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError("Не удалось прочитать PDF — файл повреждён") from exc


def _extract_docx(content: bytes) -> str:
    """Извлекает параграфы и таблицы DOCX."""
    from docx import Document

    _check_archive(content)
    try:
        document = Document(io.BytesIO(content))
    except Exception as exc:
        raise DocumentError("Не удалось прочитать DOCX — файл повреждён") from exc

    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _check_archive(content: bytes) -> None:
    """Не даёт DOCX-архиву распаковаться в гигантский объём."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            total = sum(info.file_size for info in archive.infolist())
    except zipfile.BadZipFile as exc:
        raise DocumentError("Не удалось прочитать DOCX — файл повреждён") from exc
    if total > MAX_ARCHIVE_BYTES:
        raise DocumentError("DOCX слишком большой после распаковки — загрузите текст вручную")


def _clean_text(text: str) -> str:
    """Схлопывает лишние пустые строки и пробелы по краям."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned.strip()
