"""drop assessment subsystem

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-11-05 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: str | Sequence[str] | None = "d7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Удаляет таблицы assessment и поля подтверждённого уровня."""
    op.drop_table("assessment_answers")
    op.drop_table("assessment_attempts")
    op.drop_table("assessment_questions")
    op.drop_column("user_skill_states", "claimed_level")
    op.drop_column("user_skill_states", "verified_level")
    op.drop_column("user_skill_states", "evidence_strength")


def downgrade() -> None:
    """Возвращает только поля профиля; таблицы assessment не восстанавливаются."""
    op.add_column(
        "user_skill_states", sa.Column("claimed_level", sa.Integer(), nullable=True)
    )
    op.add_column(
        "user_skill_states", sa.Column("verified_level", sa.Integer(), nullable=True)
    )
    op.add_column(
        "user_skill_states",
        sa.Column(
            "evidence_strength",
            sa.Float(),
            server_default=sa.text("0.4"),
            nullable=False,
        ),
    )
