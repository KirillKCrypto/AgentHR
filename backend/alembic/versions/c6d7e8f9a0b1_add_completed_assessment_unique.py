"""add completed assessment unique index

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-11-04 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: str | Sequence[str] | None = "b5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Запрещает более одной завершённой попытки на тему."""
    # В dev-БД могли накопиться повторные прохождения. Оставляем последнее.
    op.execute(
        """
        DELETE FROM assessment_attempts
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY user_id, topic_id
                           ORDER BY finished_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM assessment_attempts
                WHERE status = 'completed'
            ) duplicates
            WHERE duplicates.rn > 1
        )
        """
    )
    op.create_index(
        "uq_assessment_attempt_completed",
        "assessment_attempts",
        ["user_id", "topic_id"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )


def downgrade() -> None:
    """Удаляет ограничение повторного прохождения."""
    op.drop_index("uq_assessment_attempt_completed", table_name="assessment_attempts")
