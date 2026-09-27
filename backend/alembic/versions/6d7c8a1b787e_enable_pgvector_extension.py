"""enable pgvector extension

Revision ID: 6d7c8a1b787e
Revises:
Create Date: 2026-09-27 09:37:19.629051

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6d7c8a1b787e"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Включает расширение pgvector (векторный поиск)."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Удаляет расширение pgvector."""
    op.execute("DROP EXTENSION IF EXISTS vector")
