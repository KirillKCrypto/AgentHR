"""add vacancy interview context

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-10 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет привязку интервью к вакансии и контекст требования."""
    op.add_column("interview_sessions", sa.Column("vacancy_id", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_interview_sessions_vacancy_id", "interview_sessions", ["vacancy_id"]
    )
    op.create_foreign_key(
        "fk_interview_sessions_vacancy_id",
        "interview_sessions",
        "vacancies",
        ["vacancy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("interview_turns", sa.Column("context", sa.Text(), nullable=True))


def downgrade() -> None:
    """Удаляет контекст вакансии."""
    op.drop_column("interview_turns", "context")
    op.drop_constraint(
        "fk_interview_sessions_vacancy_id", "interview_sessions", type_="foreignkey"
    )
    op.drop_index("ix_interview_sessions_vacancy_id", table_name="interview_sessions")
    op.drop_column("interview_sessions", "vacancy_id")
