"""add provisional topics and aliases

Revision ID: b7e4c2a91f30
Revises: 40b5a867f0dc
Create Date: 2026-10-28 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e4c2a91f30"
down_revision: str | Sequence[str] | None = "40b5a867f0dc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет статусы тем, provisional-темы и таблицу алиасов."""
    op.add_column(
        "topics",
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'canonical'"), nullable=False
        ),
    )
    op.add_column(
        "topics",
        sa.Column("origin", sa.String(length=20), server_default=sa.text("'seed'"), nullable=False),
    )
    op.add_column("topics", sa.Column("canonical_topic_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_topics_canonical_topic_id",
        "topics",
        "topics",
        ["canonical_topic_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_topics_canonical_topic_id"),
        "topics",
        ["canonical_topic_id"],
        unique=False,
    )

    op.create_table(
        "topic_aliases",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("normalized_alias", sa.String(length=200), nullable=False),
        sa.Column(
            "source", sa.String(length=20), server_default=sa.text("'manual'"), nullable=False
        ),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_alias", name="uq_topic_aliases_normalized_alias"),
    )
    op.create_index(
        op.f("ix_topic_aliases_topic_id"),
        "topic_aliases",
        ["topic_id"],
        unique=False,
    )

    op.add_column("topic_candidates", sa.Column("topic_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_topic_candidates_topic_id",
        "topic_candidates",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_topic_candidates_topic_id"),
        "topic_candidates",
        ["topic_id"],
        unique=False,
    )


def downgrade() -> None:
    """Откатывает статусы, provisional-темы и таблицу алиасов."""
    op.drop_index(op.f("ix_topic_candidates_topic_id"), table_name="topic_candidates")
    op.drop_constraint("fk_topic_candidates_topic_id", "topic_candidates", type_="foreignkey")
    op.drop_column("topic_candidates", "topic_id")

    op.drop_index(op.f("ix_topic_aliases_topic_id"), table_name="topic_aliases")
    op.drop_table("topic_aliases")

    op.drop_index(op.f("ix_topics_canonical_topic_id"), table_name="topics")
    op.drop_constraint("fk_topics_canonical_topic_id", "topics", type_="foreignkey")
    op.drop_column("topics", "canonical_topic_id")
    op.drop_column("topics", "origin")
    op.drop_column("topics", "status")
