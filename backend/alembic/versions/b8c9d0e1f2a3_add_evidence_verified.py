"""add evidence type and verified level

Revision ID: b8c9d0e1f2a3
Revises: f6a7b8c9d0e1
Create Date: 2026-11-19 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет тип свидетельства и подтверждённый уровень."""
    op.add_column(
        "user_skill_states",
        sa.Column(
            "evidence_type",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'self_report'"),
        ),
    )
    op.add_column(
        "user_skill_states",
        sa.Column("verified_level", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Удаляет подтверждённые уровни."""
    op.drop_column("user_skill_states", "verified_level")
    op.drop_column("user_skill_states", "evidence_type")
