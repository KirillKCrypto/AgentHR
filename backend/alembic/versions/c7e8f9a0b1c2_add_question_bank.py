"""add question bank

Revision ID: c7e8f9a0b1c2
Revises: b6d7e8f9a0b1
Create Date: 2026-11-05 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "b6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицу вопросов."""
    op.create_table(
        "questions",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "expected_points",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=20), server_default=sa.text("'llm'"), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )
    op.create_index("ix_questions_topic_id", "questions", ["topic_id"])
    op.create_index("ix_questions_fingerprint", "questions", ["fingerprint"])
    op.create_index(
        "ix_questions_topic_difficulty", "questions", ["topic_id", "difficulty"]
    )


def downgrade() -> None:
    """Удаляет таблицу вопросов."""
    op.drop_index("ix_questions_topic_difficulty", table_name="questions")
    op.drop_index("ix_questions_fingerprint", table_name="questions")
    op.drop_index("ix_questions_topic_id", table_name="questions")
    op.drop_table("questions")
