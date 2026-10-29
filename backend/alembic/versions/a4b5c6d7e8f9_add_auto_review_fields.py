"""add automatic ontology review fields

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-10-29 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4b5c6d7e8f9"
down_revision: str | Sequence[str] | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет состояние автоматического ревью provisional-тем."""
    op.add_column(
        "topics",
        sa.Column("auto_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "topics",
        sa.Column("auto_review_decision", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "topics",
        sa.Column("auto_review_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "topics",
        sa.Column(
            "auto_reviewed_occurrences",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Удаляет состояние автоматического ревью."""
    op.drop_column("topics", "auto_reviewed_occurrences")
    op.drop_column("topics", "auto_review_confidence")
    op.drop_column("topics", "auto_review_decision")
    op.drop_column("topics", "auto_reviewed_at")
