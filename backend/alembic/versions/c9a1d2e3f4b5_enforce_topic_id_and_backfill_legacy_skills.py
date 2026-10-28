"""enforce topic_id and backfill legacy skills

Revision ID: c9a1d2e3f4b5
Revises: b7e4c2a91f30
Create Date: 2026-10-28 19:00:00.000000

"""

import hashlib
import json
import re
import uuid
from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.ontology.topics import ONTOLOGY_VERSION
from app.services.normalization import normalize_name

# revision identifiers, used by Alembic.
revision: str = "c9a1d2e3f4b5"
down_revision: str | Sequence[str] | None = "b7e4c2a91f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _clip(value: str, limit: int) -> str:
    """Обрезает значение под размер колонки."""
    return (value or "").strip()[:limit]


def _legacy_topic_key(normalized: str, connection: sa.Connection) -> str:
    """Создаёт уникальный ключ для provisional-темы старого навыка."""
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")[:30] or "skill"
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    base = f"auto-legacy-{slug}-{digest}"[:64]
    key = base
    suffix = 1
    while connection.scalar(sa.text("SELECT 1 FROM topics WHERE key = :key"), {"key": key}):
        suffix += 1
        key = f"{base[:58]}-{suffix}"
    return key


def _load_topic_maps(
    connection: sa.Connection,
) -> tuple[dict[str, uuid.UUID], dict[str, uuid.UUID]]:
    """Строит карты exact/alias для обратного заполнения."""
    exact: dict[str, uuid.UUID] = {}
    aliases: dict[str, uuid.UUID] = {}
    rows = connection.execute(
        sa.text(
            "SELECT id, key, name, aliases FROM topics WHERE status IN ('canonical', 'provisional')"
        )
    ).mappings()
    for row in rows:
        exact.setdefault(normalize_name(row["key"]), row["id"])
        exact.setdefault(normalize_name(row["name"]), row["id"])
        for alias in row["aliases"] or []:
            aliases.setdefault(normalize_name(alias), row["id"])

    alias_rows = connection.execute(
        sa.text("SELECT topic_id, normalized_alias FROM topic_aliases WHERE status = 'active'")
    ).mappings()
    for row in alias_rows:
        aliases[row["normalized_alias"]] = row["topic_id"]
    return exact, aliases


def _insert_legacy_topic(
    connection: sa.Connection,
    raw_name: str,
    normalized: str,
) -> uuid.UUID:
    """Создаёт provisional-тему, алиас и кандидата для старого навыка."""
    key = _legacy_topic_key(normalized, connection)
    name = _clip(raw_name, 120) or normalized
    description = (
        f"Автоматически созданная тема для старого навыка «{_clip(raw_name, 200)}». "
        "Требует проверки и подтверждения."
    )
    topic_id = connection.execute(
        sa.text(
            """
            INSERT INTO topics
                (key, name, description, category, aliases, ontology_version,
                 is_auto_generated, status, origin)
            VALUES
                (:key, :name, :description, 'auto', CAST(:aliases AS jsonb),
                 :version, true, 'provisional', 'auto')
            RETURNING id
            """
        ),
        {
            "key": key,
            "name": name,
            "description": description,
            "aliases": json.dumps([_clip(raw_name, 200)], ensure_ascii=False),
            "version": ONTOLOGY_VERSION,
        },
    ).scalar_one()

    connection.execute(
        sa.text(
            """
            INSERT INTO topic_aliases
                (topic_id, alias, normalized_alias, source, status)
            VALUES (:topic_id, :alias, :normalized, 'auto', 'active')
            ON CONFLICT (normalized_alias) DO UPDATE SET
                topic_id = EXCLUDED.topic_id,
                alias = EXCLUDED.alias,
                source = 'auto',
                status = 'active'
            """
        ),
        {
            "topic_id": topic_id,
            "alias": _clip(raw_name, 200) or normalized,
            "normalized": normalized,
        },
    )

    connection.execute(
        sa.text(
            """
            INSERT INTO topic_candidates
                (name, normalized_name, suggested_description, occurrences, sources,
                 status, topic_id, ontology_version)
            VALUES
                (:name, :normalized, :description, 1, CAST(:sources AS jsonb),
                 'auto_created', :topic_id, :version)
            ON CONFLICT (normalized_name) DO UPDATE SET
                topic_id = EXCLUDED.topic_id,
                status = 'auto_created',
                suggested_description = EXCLUDED.suggested_description
            """
        ),
        {
            "name": _clip(raw_name, 200) or normalized,
            "normalized": normalized,
            "description": description,
            "sources": json.dumps(
                [{"type": "legacy", "raw_name": _clip(raw_name, 200)}],
                ensure_ascii=False,
            ),
            "topic_id": topic_id,
            "version": ONTOLOGY_VERSION,
        },
    )
    return topic_id


def _backfill_legacy_skills(connection: sa.Connection) -> None:
    """Привязывает старые NULL-навыки к canonical или provisional-темам."""
    raw_names = connection.execute(
        sa.text(
            """
            SELECT raw_name FROM resume_skills WHERE topic_id IS NULL
            UNION
            SELECT raw_name FROM vacancy_skills WHERE topic_id IS NULL
            """
        )
    ).scalars()
    raw_by_normalized: dict[str, list[str]] = defaultdict(list)
    for raw_name in raw_names:
        normalized = _clip(normalize_name(raw_name), 200) or "unknown skill"
        raw_by_normalized[normalized].append(raw_name)

    if not raw_by_normalized:
        return

    exact, aliases = _load_topic_maps(connection)
    topic_by_normalized: dict[str, uuid.UUID] = {}
    for normalized in raw_by_normalized:
        topic_id = exact.get(normalized) or aliases.get(normalized)
        if topic_id is None:
            topic_id = _insert_legacy_topic(
                connection,
                raw_by_normalized[normalized][0],
                normalized,
            )
        topic_by_normalized[normalized] = topic_id

    for normalized, names in raw_by_normalized.items():
        topic_id = topic_by_normalized[normalized]
        for raw_name in names:
            for table in ("resume_skills", "vacancy_skills"):
                connection.execute(
                    sa.text(
                        f"""
                        UPDATE {table}
                        SET topic_id = :topic_id,
                            match_method = CASE
                                WHEN match_method = 'none' THEN 'backfill'
                                ELSE match_method
                            END
                        WHERE topic_id IS NULL AND raw_name = :raw_name
                        """
                    ),
                    {"topic_id": topic_id, "raw_name": raw_name},
                )


def upgrade() -> None:
    """Заполняет старые NULL и делает topic_id обязательным."""
    connection = op.get_bind()
    _backfill_legacy_skills(connection)

    remaining = connection.scalar(
        sa.text(
            """
            SELECT
                (SELECT count(*) FROM resume_skills WHERE topic_id IS NULL)
                + (SELECT count(*) FROM vacancy_skills WHERE topic_id IS NULL)
            """
        )
    )
    if remaining:
        raise RuntimeError(f"Не удалось заполнить topic_id у {remaining} навыков")

    op.alter_column(
        "resume_skills",
        "topic_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.alter_column(
        "vacancy_skills",
        "topic_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    op.drop_constraint("resume_skills_topic_id_fkey", "resume_skills", type_="foreignkey")
    op.create_foreign_key(
        "resume_skills_topic_id_fkey",
        "resume_skills",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("vacancy_skills_topic_id_fkey", "vacancy_skills", type_="foreignkey")
    op.create_foreign_key(
        "vacancy_skills_topic_id_fkey",
        "vacancy_skills",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Возвращает nullable topic_id и старое поведение SET NULL."""
    op.drop_constraint("vacancy_skills_topic_id_fkey", "vacancy_skills", type_="foreignkey")
    op.create_foreign_key(
        "vacancy_skills_topic_id_fkey",
        "vacancy_skills",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("resume_skills_topic_id_fkey", "resume_skills", type_="foreignkey")
    op.create_foreign_key(
        "resume_skills_topic_id_fkey",
        "resume_skills",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column(
        "vacancy_skills",
        "topic_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.alter_column(
        "resume_skills",
        "topic_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
