"""add ontology review actions

Revision ID: d1e2f3a4b5c6
Revises: c9a1d2e3f4b5
Create Date: 2026-10-28 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "c9a1d2e3f4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт аудит-лог ревью онтологии."""
    op.create_table(
        "ontology_review_actions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("source_topic_id", sa.Uuid(), nullable=True),
        sa.Column("target_topic_id", sa.Uuid(), nullable=True),
        sa.Column("actor", sa.String(length=120), server_default=sa.text("'cli'"), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ontology_review_actions_source_topic_id"),
        "ontology_review_actions",
        ["source_topic_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ontology_review_actions_target_topic_id"),
        "ontology_review_actions",
        ["target_topic_id"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет аудит-лог ревью онтологии."""
    op.drop_index(
        op.f("ix_ontology_review_actions_target_topic_id"),
        table_name="ontology_review_actions",
    )
    op.drop_index(
        op.f("ix_ontology_review_actions_source_topic_id"),
        table_name="ontology_review_actions",
    )
    op.drop_table("ontology_review_actions")
