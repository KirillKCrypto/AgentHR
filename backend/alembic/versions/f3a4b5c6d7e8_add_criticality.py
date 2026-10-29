"""add requirement criticality

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-10-29 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет обязательность требования вакансии."""
    op.add_column(
        "vacancy_skills",
        sa.Column(
            "criticality",
            sa.String(length=20),
            server_default=sa.text("'must_have'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_vacancy_skills_criticality",
        "vacancy_skills",
        "criticality IN ('must_have', 'nice_to_have')",
    )


def downgrade() -> None:
    """Удаляет обязательность требования вакансии."""
    op.drop_constraint(
        "ck_vacancy_skills_criticality",
        "vacancy_skills",
        type_="check",
    )
    op.drop_column("vacancy_skills", "criticality")
