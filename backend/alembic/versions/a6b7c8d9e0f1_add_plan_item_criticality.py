"""add criticality to plan items

Revision ID: a6b7c8d9e0f1
Revises: f4a5b6c7d8e9
Create Date: 2026-11-27 00:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6b7c8d9e0f1"
down_revision: str | Sequence[str] | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет критичность темы плана и заполняет её из вакансии."""
    op.add_column(
        "plan_items",
        sa.Column(
            "criticality",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'nice_to_have'"),
        ),
    )
    op.execute(
        """
        UPDATE plan_items
        SET criticality = 'must_have'
        WHERE EXISTS (
            SELECT 1
            FROM learning_plans
            JOIN vacancy_skills
              ON vacancy_skills.vacancy_id = learning_plans.vacancy_id
             AND vacancy_skills.topic_id = plan_items.topic_id
            WHERE learning_plans.id = plan_items.plan_id
              AND vacancy_skills.criticality = 'must_have'
        )
        """
    )


def downgrade() -> None:
    """Удаляет критичность темы плана."""
    op.drop_column("plan_items", "criticality")
