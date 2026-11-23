"""add resume history and content hashes

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-11-23 10:00:00.000000

"""

import hashlib
import re
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def _content_hash(text: str) -> str:
    """Тот же хеш, что и в `app.services.content_hash`."""
    normalized = _WHITESPACE_RE.sub(" ", text.strip()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def upgrade() -> None:
    """Добавляет историю резюме и защиту от повторных документов."""
    op.add_column("resumes", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column(
        "resumes",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("vacancies", sa.Column("content_hash", sa.String(64), nullable=True))

    connection = op.get_bind()
    for table in ("resumes", "vacancies"):
        rows = connection.execute(sa.text(f"SELECT id, raw_text FROM {table}")).all()
        for row in rows:
            connection.execute(
                sa.text(f"UPDATE {table} SET content_hash = :hash WHERE id = :id"),
                {"hash": _content_hash(row.raw_text), "id": row.id},
            )

    # Старое поведение смешивало все резюме: активным делаем последнее.
    connection.execute(
        sa.text(
            """
            UPDATE resumes AS resume
            SET is_active = true
            FROM (
                SELECT DISTINCT ON (user_id) id
                FROM resumes
                ORDER BY user_id, created_at DESC, id DESC
            ) AS latest
            WHERE resume.id = latest.id
            """
        )
    )

    op.create_index("ix_resumes_content_hash", "resumes", ["content_hash"])
    op.create_index("ix_resumes_is_active", "resumes", ["is_active"])
    op.create_index(
        "uq_resumes_active_user",
        "resumes",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index("ix_vacancies_content_hash", "vacancies", ["content_hash"])


def downgrade() -> None:
    """Удаляет историю резюме и хеши содержимого."""
    op.drop_index("ix_vacancies_content_hash", table_name="vacancies")
    op.drop_index("uq_resumes_active_user", table_name="resumes")
    op.drop_index("ix_resumes_is_active", table_name="resumes")
    op.drop_index("ix_resumes_content_hash", table_name="resumes")
    op.drop_column("vacancies", "content_hash")
    op.drop_column("resumes", "is_active")
    op.drop_column("resumes", "content_hash")
