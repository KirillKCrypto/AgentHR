"""add requirement groups

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-29 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет группы и логику требований вакансии."""
    op.add_column(
        "vacancy_skills",
        sa.Column("requirement_group", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "vacancy_skills",
        sa.Column(
            "requirement_logic",
            sa.String(length=10),
            server_default=sa.text("'SINGLE'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_vacancy_skills_requirement_logic",
        "vacancy_skills",
        "requirement_logic IN ('SINGLE', 'AND', 'OR')",
    )


def downgrade() -> None:
    """Удаляет группы и логику требований вакансии."""
    op.drop_constraint(
        "ck_vacancy_skills_requirement_logic",
        "vacancy_skills",
        type_="check",
    )
    op.drop_column("vacancy_skills", "requirement_logic")
    op.drop_column("vacancy_skills", "requirement_group")
