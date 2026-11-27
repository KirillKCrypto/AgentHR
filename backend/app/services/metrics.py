"""Единые метрики навыков, плана и готовности к вакансии."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Resume, ResumeSkill, UserSkillState


async def load_self_levels(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> dict[uuid.UUID, int]:
    """Уровни самооценки: активное резюме и ручные правки.

    Берём максимум по источнику: резюме описывает кандидата, ручная
    корректировка считается более осознанной.
    """
    levels: dict[uuid.UUID, int] = {}
    resume_rows = (
        await session.execute(
            select(ResumeSkill.topic_id, ResumeSkill.proficiency)
            .join(Resume, Resume.id == ResumeSkill.resume_id)
            .where(
                Resume.user_id == user_id,
                Resume.is_active.is_(True),
                ResumeSkill.topic_id.is_not(None),
            )
        )
    ).all()
    for topic_id, proficiency in resume_rows:
        if topic_id is None:
            continue
        levels[topic_id] = max(levels.get(topic_id, 0), proficiency)

    manual_rows = (
        await session.execute(
            select(UserSkillState.topic_id, UserSkillState.proficiency).where(
                UserSkillState.user_id == user_id,
                UserSkillState.source == "manual",
            )
        )
    ).all()
    for topic_id, proficiency in manual_rows:
        levels[topic_id] = max(levels.get(topic_id, 0), proficiency)
    return levels


def skill_status(required_level: int, verified_level: int, self_level: int) -> str:
    """Статус подтверждения навыка."""
    if required_level <= 0:
        return "confirmed"
    if verified_level >= required_level:
        return "confirmed"
    if verified_level > 0:
        return "partial"
    if self_level > 0:
        return "self_only"
    return "unverified"


def readiness_band(
    verified_readiness: float | None,
    critical_verified: float | None,
    potential_readiness: float,
    evidence_coverage: float,
) -> tuple[str, str]:
    """Возвращает бэнд готовности и короткое объяснение."""
    if verified_readiness is None:
        return "not_ready", "Нет подтверждённых требований для расчёта."

    critical = 1.0 if critical_verified is None else critical_verified
    if verified_readiness >= 0.8 and critical >= 1.0 and evidence_coverage >= 0.8:
        return "ready", "Подтверждённая готовность высокая, обязательные требования закрыты."
    if verified_readiness >= 0.6 and critical >= 0.8:
        return "almost", "Подтверждённая база есть, остались отдельные обязательные пробелы."
    if potential_readiness >= 0.6 and verified_readiness < 0.6:
        return (
            "needs_confirmation",
            "Резюме показывает потенциал, но тесты пока не подтверждают уровень.",
        )
    return "not_ready", "Подтверждённых знаний недостаточно для требований вакансии."
