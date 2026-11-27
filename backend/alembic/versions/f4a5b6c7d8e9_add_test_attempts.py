"""add attempts to topic test results

Revision ID: f4a5b6c7d8e9
Revises: e1f2a3b4c5d6
Create Date: 2026-11-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет номер попытки и новое ограничение уникальности."""
    op.add_column(
        "topic_test_results",
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.drop_constraint(
        "uq_topic_test_results_user_topic",
        "topic_test_results",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_topic_test_results_user_topic_attempt",
        "topic_test_results",
        ["user_id", "topic_id", "attempt_no"],
    )
    # План без вакансии теперь целится в 80, а не в недостижимые 100.
    op.execute(
        """
        UPDATE plan_items
        SET target_level = 80
        FROM learning_plans
        WHERE plan_items.plan_id = learning_plans.id
          AND learning_plans.vacancy_id IS NULL
          AND plan_items.target_level = 100
        """
    )


def downgrade() -> None:
    """Возвращает одну попытку на тему."""
    op.drop_constraint(
        "uq_topic_test_results_user_topic_attempt",
        "topic_test_results",
        type_="unique",
    )
    # Перед возвратом старого ограничения оставляем только первую попытку.
    op.execute(
        "DELETE FROM topic_test_results WHERE attempt_no > 1"
    )
    op.create_unique_constraint(
        "uq_topic_test_results_user_topic",
        "topic_test_results",
        ["user_id", "topic_id"],
    )
    op.drop_column("topic_test_results", "attempt_no")
