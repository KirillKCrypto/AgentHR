"""add interview answer timer and mode

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет таймер и режим ответа."""
    op.add_column(
        "interview_sessions",
        sa.Column("answer_seconds", sa.Integer(), nullable=False, server_default=sa.text("300")),
    )
    op.add_column(
        "interview_turns",
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_turns",
        sa.Column("answer_mode", sa.String(length=20), nullable=False, server_default=sa.text("'text'")),
    )


def downgrade() -> None:
    """Удаляет таймер и режим ответа."""
    op.drop_column("interview_turns", "answer_mode")
    op.drop_column("interview_turns", "deadline_at")
    op.drop_column("interview_sessions", "answer_seconds")
