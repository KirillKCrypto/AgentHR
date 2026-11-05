"""add quiz options to questions

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-11-05 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет варианты ответа и пояснение к вопросам."""
    op.add_column(
        "questions",
        sa.Column(
            "options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("questions", sa.Column("correct_option", sa.Integer(), nullable=True))
    op.add_column("questions", sa.Column("explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    """Удаляет варианты ответа."""
    op.drop_column("questions", "explanation")
    op.drop_column("questions", "correct_option")
    op.drop_column("questions", "options")
