"""add review schedule

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-11-19 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет расписание повторения темы."""
    op.add_column(
        "user_skill_states",
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_skill_states",
        sa.Column("review_interval_days", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )


def downgrade() -> None:
    """Удаляет расписание повторения."""
    op.drop_column("user_skill_states", "review_interval_days")
    op.drop_column("user_skill_states", "review_due_at")
