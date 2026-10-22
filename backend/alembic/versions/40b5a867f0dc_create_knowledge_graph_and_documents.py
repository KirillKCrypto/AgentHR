"""create knowledge graph and documents tables

Revision ID: 40b5a867f0dc
Revises: 22cd6bbf10ed
Create Date: 2026-10-22 10:20:37.469553

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "40b5a867f0dc"
down_revision: str | Sequence[str] | None = "22cd6bbf10ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицы графа знаний, документов и среза профиля."""
    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column(
            "aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("ontology_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "is_auto_generated", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_topics_key"), "topics", ["key"], unique=True)

    op.create_table(
        "topic_prerequisites",
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("prerequisite_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("topic_id <> prerequisite_id", name="ck_topic_prerequisites_not_self"),
        sa.ForeignKeyConstraint(["prerequisite_id"], ["topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("topic_id", "prerequisite_id"),
    )

    op.create_table(
        "topic_candidates",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("suggested_description", sa.Text(), nullable=True),
        sa.Column("occurrences", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'new'"), nullable=False),
        sa.Column("ontology_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name", name="uq_topic_candidates_normalized_name"),
    )
    op.create_index(
        op.f("ix_topic_candidates_normalized_name"),
        "topic_candidates",
        ["normalized_name"],
        unique=False,
    )

    op.create_table(
        "vacancies",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "source", sa.String(length=20), server_default=sa.text("'manual'"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vacancies_user_id"), "vacancies", ["user_id"], unique=False)

    op.create_table(
        "vacancy_skills",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=True),
        sa.Column("raw_name", sa.String(length=200), nullable=False),
        sa.Column("required_level", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("weight", sa.Float(), server_default=sa.text("1.0"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.5"), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column(
            "match_method", sa.String(length=20), server_default=sa.text("'none'"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "required_level >= 0 AND required_level <= 100", name="ck_vacancy_skills_level"
        ),
        sa.CheckConstraint("weight >= 0 AND weight <= 1", name="ck_vacancy_skills_weight"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_vacancy_skills_confidence"
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_vacancy_skills_vacancy_id"), "vacancy_skills", ["vacancy_id"], unique=False
    )
    op.create_index(
        op.f("ix_vacancy_skills_topic_id"), "vacancy_skills", ["topic_id"], unique=False
    )
    op.create_index(
        "ix_vacancy_skills_vacancy_topic",
        "vacancy_skills",
        ["vacancy_id", "topic_id"],
        unique=False,
    )

    op.create_table(
        "resumes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resumes_user_id"), "resumes", ["user_id"], unique=False)

    op.create_table(
        "resume_skills",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=True),
        sa.Column("raw_name", sa.String(length=200), nullable=False),
        sa.Column("proficiency", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.5"), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column(
            "match_method", sa.String(length=20), server_default=sa.text("'none'"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "proficiency >= 0 AND proficiency <= 100", name="ck_resume_skills_proficiency"
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_resume_skills_confidence"
        ),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_resume_skills_resume_id"), "resume_skills", ["resume_id"], unique=False
    )
    op.create_index(op.f("ix_resume_skills_topic_id"), "resume_skills", ["topic_id"], unique=False)
    op.create_index(
        "ix_resume_skills_resume_topic", "resume_skills", ["resume_id", "topic_id"], unique=False
    )

    op.create_table(
        "user_skill_states",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("proficiency", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.5"), nullable=False),
        sa.Column(
            "source", sa.String(length=30), server_default=sa.text("'resume'"), nullable=False
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_assessed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "proficiency >= 0 AND proficiency <= 100", name="ck_user_skill_states_proficiency"
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_user_skill_states_confidence"
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "topic_id", name="uq_user_skill_states_user_topic"),
    )
    op.create_index(
        op.f("ix_user_skill_states_user_id"), "user_skill_states", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_user_skill_states_topic_id"), "user_skill_states", ["topic_id"], unique=False
    )


def downgrade() -> None:
    """Удаляет таблицы графа знаний, документов и среза профиля."""
    op.drop_index(op.f("ix_user_skill_states_topic_id"), table_name="user_skill_states")
    op.drop_index(op.f("ix_user_skill_states_user_id"), table_name="user_skill_states")
    op.drop_table("user_skill_states")

    op.drop_index("ix_resume_skills_resume_topic", table_name="resume_skills")
    op.drop_index(op.f("ix_resume_skills_topic_id"), table_name="resume_skills")
    op.drop_index(op.f("ix_resume_skills_resume_id"), table_name="resume_skills")
    op.drop_table("resume_skills")

    op.drop_index(op.f("ix_resumes_user_id"), table_name="resumes")
    op.drop_table("resumes")

    op.drop_index("ix_vacancy_skills_vacancy_topic", table_name="vacancy_skills")
    op.drop_index(op.f("ix_vacancy_skills_topic_id"), table_name="vacancy_skills")
    op.drop_index(op.f("ix_vacancy_skills_vacancy_id"), table_name="vacancy_skills")
    op.drop_table("vacancy_skills")

    op.drop_index(op.f("ix_vacancies_user_id"), table_name="vacancies")
    op.drop_table("vacancies")

    op.drop_index(op.f("ix_topic_candidates_normalized_name"), table_name="topic_candidates")
    op.drop_table("topic_candidates")

    op.drop_table("topic_prerequisites")

    op.drop_index(op.f("ix_topics_key"), table_name="topics")
    op.drop_table("topics")
