"""add vacancy level

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-10 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет уровень позиции к вакансии."""
    op.add_column("vacancies", sa.Column("level", sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Удаляет уровень позиции."""
    op.drop_column("vacancies", "level")
