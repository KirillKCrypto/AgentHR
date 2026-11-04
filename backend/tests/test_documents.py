"""Извлечение текста из PDF/DOCX и загрузка резюме файлом."""

import io

import pytest
from docx import Document
from pypdf import PdfWriter

from app.services.documents import MAX_UPLOAD_BYTES, DocumentError, extract_resume_text
from tests.conftest import ApiUser


def _docx_bytes(*paragraphs: str) -> bytes:
    """Собирает минимальный DOCX с заданными абзацами."""
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


def _empty_pdf_bytes() -> bytes:
    """PDF из одной пустой страницы: текстового слоя нет."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_extracts_text_from_docx() -> None:
    """DOCX: параграфы и таблицы попадают в текст."""
    document = Document()
    document.add_paragraph("Python-разработчик с опытом в FastAPI и PostgreSQL.")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Навык"
    table.rows[0].cells[1].text = "Docker"
    stream = io.BytesIO()
    document.save(stream)

    text = extract_resume_text("resume.docx", stream.getvalue())

    assert "Python-разработчик" in text
    assert "Docker" in text


def test_rejects_unsupported_extension() -> None:
    """Форматы кроме PDF/DOCX отклоняются."""
    with pytest.raises(DocumentError, match="PDF и DOCX"):
        extract_resume_text("resume.txt", b"plain text")


def test_rejects_empty_file() -> None:
    """Пустой файл отклоняется."""
    with pytest.raises(DocumentError, match="пустой"):
        extract_resume_text("resume.pdf", b"")


def test_rejects_too_large_file() -> None:
    """Файл больше лимита отклоняется до парсинга."""
    with pytest.raises(DocumentError, match="МБ"):
        extract_resume_text("resume.pdf", b"x" * (MAX_UPLOAD_BYTES + 1))


def test_rejects_pdf_without_text_layer() -> None:
    """PDF без текстового слоя даёт понятную ошибку вместо пустого резюме."""
    with pytest.raises(DocumentError, match="только изображения"):
        extract_resume_text("scan.pdf", _empty_pdf_bytes())


def test_rejects_corrupted_docx() -> None:
    """Битый DOCX не роняет запрос."""
    with pytest.raises(DocumentError, match="DOCX"):
        extract_resume_text("broken.docx", b"not a zip archive")


async def test_upload_docx_resume_returns_skills(api_user: ApiUser) -> None:
    """POST /resumes/upload сохраняет резюме и извлекает навыки."""
    name = "File Upload Skill"
    api_user.provider.responses["resume_skills"] = {
        "experience_years": 2.0,
        "self_level": "middle",
        "skills": [
            {
                "name": name,
                "proficiency": 60,
                "evidence": "из файла",
                "confidence": 0.8,
            }
        ],
    }
    content = _docx_bytes("Резюме с навыком File Upload Skill и опытом работы.")

    response = await api_user.client.post(
        "/resumes/upload",
        files={
            "file": (
                "resume.docx",
                content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"title": "Резюме из файла"},
        headers=api_user.headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Резюме из файла"
    assert body["skills"][0]["raw_name"] == name


async def test_upload_pdf_without_text_returns_422(api_user: ApiUser) -> None:
    """Скан без текста отклоняется с 422, резюме не создаётся."""
    response = await api_user.client.post(
        "/resumes/upload",
        files={"file": ("scan.pdf", _empty_pdf_bytes(), "application/pdf")},
        headers=api_user.headers,
    )

    assert response.status_code == 422
    assert "изображения" in response.json()["detail"]


async def test_upload_too_large_returns_413(api_user: ApiUser) -> None:
    """Файл сверх лимита обрывается до сохранения резюме."""
    response = await api_user.client.post(
        "/resumes/upload",
        files={"file": ("big.pdf", b"x" * (MAX_UPLOAD_BYTES + 1), "application/pdf")},
        headers=api_user.headers,
    )

    assert response.status_code == 413
