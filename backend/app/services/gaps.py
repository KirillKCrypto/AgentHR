"""Gap-анализ вакансии относительно профиля пользователя."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Topic, UserSkillState, Vacancy, VacancySkill
from app.services.errors import NotFoundError


@dataclass(frozen=True)
class GapItem:
    """Р Р°Р·СЂС‹РІ РјРµР¶РґСѓ С‚СЂРµР±СѓРµРјС‹Рј Рё С‚РµРєСѓС‰РёРј СѓСЂРѕРІРЅРµРј РїРѕ РѕРґРЅРѕРјСѓ РЅР°РІС‹РєСѓ."""

    skill_name: str
    required_level: int
    user_level: int
    gap: int
    satisfied: bool
    weight: float
    topic_key: str | None = None
    topic_name: str | None = None
    topic_status: str | None = None
    requirement_group: str | None = None
    requirement_logic: str = "SINGLE"
    criticality: str = "must_have"


@dataclass(frozen=True)
class GapRecommendation:
    """Р§С‚Рѕ РїРѕРґС‚СЏРЅСѓС‚СЊ РІ РїРµСЂРІСѓСЋ РѕС‡РµСЂРµРґСЊ РїРѕ РёС‚РѕРіР°Рј РІР°РєР°РЅСЃРёРё."""

    topic_key: str | None
    topic_name: str | None
    skill_name: str
    required_level: int
    user_level: int
    gap: int
    priority: float
    criticality: str
    reason: str


@dataclass(frozen=True)
class GapReport:
    """Gap-Р°РЅР°Р»РёР· РІР°РєР°РЅСЃРёРё РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РїСЂРѕС„РёР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""

    vacancy_id: uuid.UUID
    vacancy_title: str | None
    items: tuple[GapItem, ...] = ()
    overall_readiness: float = 0.0
    coverage_all: float = 0.0
    confirmed_readiness: float | None = None
    critical_readiness: float | None = None
    satisfied_count: int = 0
    requirements_count: int = 0
    average_gap: float = 0.0
    recommendations: tuple[GapRecommendation, ...] = ()
    provisional_count: int = 0
    provisional_weight: float = 0.0
    confirmed_weight: float = 0.0
    critical_count: int = 0
    critical_weight: float = 0.0
    critical_gap_count: int = 0
    unmatched_count: int = 0

async def compute_gaps(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy_id: uuid.UUID,
) -> GapReport:
    """РЎС‡РёС‚Р°РµС‚ СЂР°Р·СЂС‹РІС‹ РјРµР¶РґСѓ С‚СЂРµР±РѕРІР°РЅРёСЏРјРё РІР°РєР°РЅСЃРёРё Рё РїСЂРѕС„РёР»РµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.

    Р“РѕС‚РѕРІРЅРѕСЃС‚СЊ СЃС‡РёС‚Р°РµС‚СЃСЏ С‚РѕР»СЊРєРѕ РїРѕ РЅР°РІС‹РєР°Рј, СЃРѕРїРѕСЃС‚Р°РІР»РµРЅРЅС‹Рј СЃ РѕРЅС‚РѕР»РѕРіРёРµР№:
    РґР»СЏ РЅР°РІС‹РєРѕРІ РІРЅРµ СЃР»РѕРІР°СЂСЏ РЅРµС‚ РґРѕСЃС‚РѕРІРµСЂРЅРѕР№ РѕС†РµРЅРєРё СѓСЂРѕРІРЅСЏ, РїРѕСЌС‚РѕРјСѓ РѕРЅРё
    РїРѕРєР°Р·С‹РІР°СЋС‚СЃСЏ РІ СЂР°Р·СЂС‹РІР°С…, РЅРѕ РЅРµ РёСЃРєР°Р¶Р°СЋС‚ РѕР±С‰РёР№ РїСЂРѕС†РµРЅС‚.
    """
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.user_id != user_id:
        raise NotFoundError("Вакансия не найдена")

    skills = (
        await session.scalars(
            select(VacancySkill)
            .where(VacancySkill.vacancy_id == vacancy.id)
            .order_by(VacancySkill.weight.desc(), VacancySkill.raw_name)
        )
    ).all()
    topics = {topic.id: topic for topic in (await session.scalars(select(Topic))).all()}
    states = {
        state.topic_id: state
        for state in (
            await session.scalars(select(UserSkillState).where(UserSkillState.user_id == user_id))
        ).all()
    }

    items: list[GapItem] = []
    calculations: list[tuple[VacancySkill, GapItem, float, str | None]] = []
    provisional_count = 0
    provisional_weight = 0.0
    critical_count = 0
    critical_weight = 0.0
    critical_gap_count = 0
    unmatched_count = 0
    weighted_gap_total = 0.0
    weighted_gap_weight = 0.0

    for skill in skills:
        topic = topics.get(skill.topic_id) if skill.topic_id is not None else None
        state = states.get(skill.topic_id) if skill.topic_id is not None else None
        user_level = state.proficiency if state is not None else 0
        gap = max(0, skill.required_level - user_level)
        topic_status = topic.status if topic is not None else None
        logic = skill.requirement_logic or "SINGLE"
        criticality = skill.criticality or "must_have"
        if criticality == "must_have":
            critical_count += 1
            critical_weight += skill.weight
            if gap > 0:
                critical_gap_count += 1

        item = GapItem(
            skill_name=skill.raw_name,
            required_level=skill.required_level,
            user_level=user_level,
            gap=gap,
            satisfied=gap == 0,
            weight=skill.weight,
            topic_key=topic.key if topic is not None else None,
            topic_name=topic.name if topic is not None else None,
            topic_status=topic_status,
            requirement_group=skill.requirement_group,
            requirement_logic=logic,
            criticality=criticality,
        )
        items.append(item)
        weighted_gap_total += skill.weight * gap
        weighted_gap_weight += skill.weight

        if topic is None or topic_status not in ("canonical", "provisional"):
            unmatched_count += 1
            calculations.append((skill, item, 0.0, topic_status))
            continue

        ratio = 1.0 if skill.required_level <= 0 else min(1.0, user_level / skill.required_level)
        calculations.append((skill, item, ratio, topic_status))
        if topic_status == "provisional":
            provisional_count += 1
            provisional_weight += skill.weight

    grouped: dict[str, list[tuple[VacancySkill, GapItem, float, str | None]]] = {}
    for calculation in calculations:
        skill = calculation[0]
        logic = skill.requirement_logic or "SINGLE"
        if skill.requirement_group and logic in ("AND", "OR"):
            key = f"group:{skill.requirement_group}"
        else:
            key = f"skill:{skill.id}"
        grouped.setdefault(key, []).append(calculation)

    weighted_all_done = 0.0
    weighted_all_total = 0.0
    weighted_confirmed_done = 0.0
    confirmed_weight = 0.0
    weighted_critical_done = 0.0
    critical_metric_weight = 0.0

    for group in grouped.values():
        logic = group[0][0].requirement_logic or "SINGLE"
        ratios = [ratio for _, _, ratio, _ in group]
        weights = [item.weight for _, item, _, _ in group]
        if logic == "OR":
            group_ratio = max(ratios)
            group_weight = max(weights)
        elif logic == "AND":
            group_ratio = min(ratios)
            group_weight = sum(weights)
        else:
            group_ratio = ratios[0]
            group_weight = weights[0]

        weighted_all_done += group_weight * group_ratio
        weighted_all_total += group_weight

        if all(topic_status == "canonical" for _, _, _, topic_status in group):
            weighted_confirmed_done += group_weight * group_ratio
            confirmed_weight += group_weight

        if any(item.criticality == "must_have" for _, item, _, _ in group):
            weighted_critical_done += group_weight * group_ratio
            critical_metric_weight += group_weight

    if weighted_all_total > 0:
        coverage_all = weighted_all_done / weighted_all_total
    else:
        # РќР°РІС‹РєРѕРІ РІРЅРµ РѕРЅС‚РѕР»РѕРіРёРё РЅРµС‚, Р° С‚СЂРµР±РѕРІР°РЅРёР№ РЅРµС‚ РІРѕРІСЃРµ вЂ” РїРѕРєСЂС‹С‚РёРµ РїРѕР»РЅРѕРµ
        coverage_all = 1.0 if not skills else 0.0

    confirmed_readiness = (
        round(weighted_confirmed_done / confirmed_weight, 3) if confirmed_weight > 0 else None
    )
    critical_readiness = (
        round(weighted_critical_done / critical_metric_weight, 3)
        if critical_metric_weight > 0
        else None
    )
    average_gap = (
        round(weighted_gap_total / weighted_gap_weight, 1) if weighted_gap_weight > 0 else 0.0
    )

    return GapReport(
        vacancy_id=vacancy.id,
        vacancy_title=vacancy.title,
        items=tuple(items),
        overall_readiness=round(coverage_all, 3),
        coverage_all=round(coverage_all, 3),
        confirmed_readiness=confirmed_readiness,
        critical_readiness=critical_readiness,
        satisfied_count=sum(1 for item in items if item.satisfied),
        requirements_count=len(items),
        average_gap=average_gap,
        recommendations=_recommendations(items),
        provisional_count=provisional_count,
        provisional_weight=round(provisional_weight, 3),
        confirmed_weight=round(confirmed_weight, 3),
        critical_count=critical_count,
        critical_weight=round(critical_weight, 3),
        critical_gap_count=critical_gap_count,
        unmatched_count=unmatched_count,
    )

def _recommendations(items: list[GapItem], limit: int = 5) -> tuple[GapRecommendation, ...]:
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ РґРѕ `limit` С‚РµРј, РєРѕС‚РѕСЂС‹Рµ РЅСѓР¶РЅРѕ РїРѕРґС‚СЏРЅСѓС‚СЊ РІ РїРµСЂРІСѓСЋ РѕС‡РµСЂРµРґСЊ."""
    ranked: list[tuple[float, GapItem]] = []
    for item in items:
        if item.satisfied or item.required_level <= 0:
            continue
        factor = 1.0 if item.criticality == "must_have" else 0.5
        priority = factor * item.weight * (item.gap / item.required_level)
        if priority <= 0:
            continue
        ranked.append((round(priority, 3), item))

    ranked.sort(key=lambda pair: (pair[0], pair[1].gap), reverse=True)

    result: list[GapRecommendation] = []
    seen: set[str] = set()
    for priority, item in ranked:
        key = item.topic_key or item.skill_name
        if key in seen:
            continue
        seen.add(key)
        criticality = "РѕР±СЏР·Р°С‚РµР»СЊРЅРѕРµ" if item.criticality == "must_have" else "Р¶РµР»Р°С‚РµР»СЊРЅРѕРµ"
        result.append(
            GapRecommendation(
                topic_key=item.topic_key,
                topic_name=item.topic_name,
                skill_name=item.skill_name,
                required_level=item.required_level,
                user_level=item.user_level,
                gap=item.gap,
                priority=priority,
                criticality=item.criticality,
                reason=(
                    f"{criticality.capitalize()} С‚СЂРµР±РѕРІР°РЅРёРµ, РІРµСЃ {item.weight:.2f}: "
                    f"РЅРµ С…РІР°С‚Р°РµС‚ {item.gap} РёР· {item.required_level}"
                ),
            )
        )
        if len(result) >= limit:
            break
    return tuple(result)