"""create agent_actions table

Revision ID: 22cd6bbf10ed
Revises: 68cf3aa5da9d
Create Date: 2026-09-27 10:50:30.466837

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "22cd6bbf10ed"
down_revision: str | Sequence[str] | None = "68cf3aa5da9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицу аудит-лога действий агента."""
    op.create_table(
        "agent_actions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=True),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_actions_session_id"), "agent_actions", ["session_id"], unique=False
    )


def downgrade() -> None:
    """Удаляет таблицу аудит-лога."""
    op.drop_index(op.f("ix_agent_actions_session_id"), table_name="agent_actions")
    op.drop_table("agent_actions")
