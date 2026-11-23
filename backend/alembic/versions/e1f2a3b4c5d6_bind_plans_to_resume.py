"""bind learning plans to the active resume

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-11-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет ссылку плана на резюме."""
    op.add_column("learning_plans", sa.Column("resume_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_learning_plans_resume_id_resumes",
        "learning_plans",
        "resumes",
        ["resume_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_learning_plans_resume_id", "learning_plans", ["resume_id"])


def downgrade() -> None:
    """Удаляет ссылку плана на резюме."""
    op.drop_index("ix_learning_plans_resume_id", table_name="learning_plans")
    op.drop_constraint(
        "fk_learning_plans_resume_id_resumes",
        "learning_plans",
        type_="foreignkey",
    )
    op.drop_column("learning_plans", "resume_id")
