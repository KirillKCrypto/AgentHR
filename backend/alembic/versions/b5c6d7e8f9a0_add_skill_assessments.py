"""add skill assessments

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-11-04 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f9a0"
down_revision: str | Sequence[str] | None = "c7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет банк вопросов и попытки мини-тестов."""
    op.add_column("user_skill_states", sa.Column("claimed_level", sa.Integer(), nullable=True))
    op.add_column("user_skill_states", sa.Column("verified_level", sa.Integer(), nullable=True))
    op.add_column(
        "user_skill_states",
        sa.Column(
            "evidence_strength",
            sa.Float(),
            server_default=sa.text("0.4"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_user_skill_states_claimed_level",
        "user_skill_states",
        "claimed_level IS NULL OR (claimed_level >= 0 AND claimed_level <= 100)",
    )
    op.create_check_constraint(
        "ck_user_skill_states_verified_level",
        "user_skill_states",
        "verified_level IS NULL OR (verified_level >= 0 AND verified_level <= 100)",
    )
    op.create_check_constraint(
        "ck_user_skill_states_evidence_strength",
        "user_skill_states",
        "evidence_strength >= 0 AND evidence_strength <= 1",
    )
    op.execute(
        "UPDATE user_skill_states SET claimed_level = proficiency "
        "WHERE claimed_level IS NULL AND source = 'resume'"
    )

    op.create_table(
        "assessment_questions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.String(length=30),
            server_default=sa.text("'single_choice'"),
            nullable=False,
        ),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column(
            "options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("correct_key", sa.String(length=20), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "difficulty >= 0 AND difficulty <= 100",
            name="ck_assessment_questions_difficulty",
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_assessment_questions_key"),
    )
    op.create_index(
        op.f("ix_assessment_questions_key"),
        "assessment_questions",
        ["key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessment_questions_topic_id"),
        "assessment_questions",
        ["topic_id"],
        unique=False,
    )

    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'in_progress'"),
            nullable=False,
        ),
        sa.Column(
            "question_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("test_level", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assessment_attempts_topic_id"),
        "assessment_attempts",
        ["topic_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessment_attempts_user_id"),
        "assessment_attempts",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "assessment_answers",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("answer_key", sa.String(length=20), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["assessment_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_assessment_answers_attempt_question",
        ),
    )
    op.create_index(
        op.f("ix_assessment_answers_attempt_id"),
        "assessment_answers",
        ["attempt_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessment_answers_question_id"),
        "assessment_answers",
        ["question_id"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет мини-тесты и поля claimed/verified."""
    op.drop_index(op.f("ix_assessment_answers_question_id"), table_name="assessment_answers")
    op.drop_index(op.f("ix_assessment_answers_attempt_id"), table_name="assessment_answers")
    op.drop_table("assessment_answers")
    op.drop_index(op.f("ix_assessment_attempts_user_id"), table_name="assessment_attempts")
    op.drop_index(op.f("ix_assessment_attempts_topic_id"), table_name="assessment_attempts")
    op.drop_table("assessment_attempts")
    op.drop_index(op.f("ix_assessment_questions_topic_id"), table_name="assessment_questions")
    op.drop_index(op.f("ix_assessment_questions_key"), table_name="assessment_questions")
    op.drop_table("assessment_questions")

    op.drop_constraint(
        "ck_user_skill_states_evidence_strength",
        "user_skill_states",
        type_="check",
    )
    op.drop_constraint(
        "ck_user_skill_states_verified_level",
        "user_skill_states",
        type_="check",
    )
    op.drop_constraint(
        "ck_user_skill_states_claimed_level",
        "user_skill_states",
        type_="check",
    )
    op.drop_column("user_skill_states", "evidence_strength")
    op.drop_column("user_skill_states", "verified_level")
    op.drop_column("user_skill_states", "claimed_level")
