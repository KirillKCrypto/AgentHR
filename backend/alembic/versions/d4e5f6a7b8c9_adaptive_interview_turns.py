"""adaptive interview turns

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-15 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет очередь тем, бюджет вопросов и follow-up."""
    op.add_column(
        "interview_sessions",
        sa.Column("max_questions", sa.Integer(), nullable=False, server_default=sa.text("8")),
    )
    op.add_column(
        "interview_sessions",
        sa.Column(
            "topic_plan",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "interview_turns",
        sa.Column("kind", sa.String(length=20), nullable=False, server_default=sa.text("'base'")),
    )
    op.add_column("interview_turns", sa.Column("parent_turn_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_interview_turns_parent_turn_id",
        "interview_turns",
        "interview_turns",
        ["parent_turn_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Удаляет адаптивные поля."""
    op.drop_constraint(
        "fk_interview_turns_parent_turn_id", "interview_turns", type_="foreignkey"
    )
    op.drop_column("interview_turns", "parent_turn_id")
    op.drop_column("interview_turns", "kind")
    op.drop_column("interview_sessions", "topic_plan")
    op.drop_column("interview_sessions", "max_questions")
