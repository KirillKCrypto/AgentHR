"""add plan profile fingerprint

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-11-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет отпечаток профиля к плану."""
    op.add_column(
        "learning_plans",
        sa.Column("profile_fingerprint", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Удаляет отпечаток профиля."""
    op.drop_column("learning_plans", "profile_fingerprint")
