"""Gap-анализ вакансии относительно профиля пользователя."""

import uuid
from dataclasses import dataclass, replace

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Topic,
    TopicTestResult,
    UserSkillState,
    Vacancy,
    VacancySkill,
)
from app.services.errors import NotFoundError
from app.services.metrics import load_self_levels, readiness_band, skill_status


@dataclass(frozen=True)
class GapItem:
    """Разрыв между требуемым и текущим уровнем по одному навыку."""

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
    # Навык не закрыт сам, но его OR-группу закрыла альтернатива.
    covered_by_alternative: bool = False
    self_level: int = 0
    verified_level: int = 0
    verified_gap: int = 0
    verified_satisfied: bool = False
    status: str = "unverified"
    evidence_type: str = "none"
    confidence: float = 0.0


@dataclass(frozen=True)
class GapRecommendation:
    """Что подтянуть в первую очередь по итогам вакансии."""

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
class GapBlocker:
    """Обязательное требование, которое мешает готовности."""

    skill_name: str
    topic_key: str | None
    topic_name: str | None
    required_level: int
    verified_level: int
    gap: int
    weight: float
    criticality: str = "must_have"


@dataclass(frozen=True)
class GapConfirmation:
    """Навык, подтверждение которого уточнит расчёт."""

    skill_name: str
    topic_key: str | None
    topic_name: str | None
    required_level: int
    self_level: int
    verified_level: int
    criticality: str
    potential_gain: float
    reason: str


@dataclass(frozen=True)
class GapReport:
    """Gap-анализ вакансии относительно профиля пользователя."""

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
    # Готовность с критическим гейтом и диапазоном уверенности.
    readiness: float = 0.0
    readiness_low: float = 0.0
    readiness_high: float = 0.0
    critical_gate: float = 1.0
    confidence: float = 0.0
    # Подтверждённая тестами и интервью готовность.
    potential_readiness: float = 0.0
    verified_readiness: float | None = None
    critical_verified: float | None = None
    evidence_coverage: float = 0.0
    band: str = "not_ready"
    band_reason: str = ""
    blockers: tuple[GapBlocker, ...] = ()
    confirmation_queue: tuple[GapConfirmation, ...] = ()


@dataclass(frozen=True)
class _Calculation:
    """Промежуточный расчёт по навыку."""

    skill: VacancySkill
    item: GapItem
    potential_ratio: float
    verified_ratio: float
    topic_status: str | None
    group_key: str


@dataclass(frozen=True)
class _GroupDetail:
    """Свёртка навыков в требование с учётом AND/OR."""

    calcs: tuple[_Calculation, ...]
    weight: float
    logic: str
    critical: bool
    potential_ratio: float
    verified_ratio: float
    potential_satisfied: bool
    verified_satisfied: bool
    verified_gap: int
    representative: GapItem


async def compute_gaps(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy_id: uuid.UUID,
) -> GapReport:
    """Считает разрывы между требованиями вакансии и профилем пользователя.

    Потенциальная готовность использует максимум из самооценки и
    подтверждений. Подтверждённая готовность использует только тесты и
    интервью: неподтверждённые требования считаются незакрытыми.
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
    self_levels = await load_self_levels(session, user_id)
    test_levels = {
        topic_id: level
        for topic_id, level in (
            await session.execute(
                select(TopicTestResult.topic_id, func.max(TopicTestResult.level))
                .where(TopicTestResult.user_id == user_id)
                .group_by(TopicTestResult.topic_id)
            )
        ).all()
    }

    items: list[GapItem] = []
    calculations: list[_Calculation] = []
    provisional_count = 0
    provisional_weight = 0.0
    critical_count = 0
    critical_weight = 0.0
    critical_gap_count = 0
    unmatched_count = 0
    weighted_gap_total = 0.0
    weighted_gap_weight = 0.0
    confidence_values: list[float] = []

    for skill in skills:
        topic = topics.get(skill.topic_id) if skill.topic_id is not None else None
        state = states.get(skill.topic_id) if skill.topic_id is not None else None
        self_level = self_levels.get(skill.topic_id, 0) if skill.topic_id is not None else 0
        state_verified = (state.verified_level or 0) if state is not None else 0
        test_verified = test_levels.get(skill.topic_id, 0) if skill.topic_id is not None else 0
        verified_level = max(state_verified, test_verified)
        effective_level = max(self_level, verified_level)
        required = skill.required_level
        gap = max(0, required - effective_level)
        verified_gap = max(0, required - verified_level)
        confidence = state.confidence if state is not None else 0.0
        confidence_values.append(confidence)
        topic_status = topic.status if topic is not None else None
        logic = skill.requirement_logic or "SINGLE"
        criticality = skill.criticality or "must_have"
        if criticality == "must_have":
            critical_count += 1
            critical_weight += skill.weight

        evidence_type = "none"
        if test_verified > 0 and test_verified >= state_verified:
            evidence_type = "test"
        elif state is not None and state_verified > 0:
            evidence_type = state.evidence_type or "interview"
        elif self_level > 0:
            evidence_type = "resume"

        item = GapItem(
            skill_name=skill.raw_name,
            required_level=required,
            user_level=effective_level,
            gap=gap,
            satisfied=gap == 0,
            weight=skill.weight,
            topic_key=topic.key if topic is not None else None,
            topic_name=topic.name if topic is not None else None,
            topic_status=topic_status,
            requirement_group=skill.requirement_group,
            requirement_logic=logic,
            criticality=criticality,
            self_level=self_level,
            verified_level=verified_level,
            verified_gap=verified_gap,
            verified_satisfied=verified_gap == 0,
            status=skill_status(required, verified_level, self_level),
            evidence_type=evidence_type,
            confidence=confidence,
        )
        items.append(item)
        weighted_gap_total += skill.weight * gap
        weighted_gap_weight += skill.weight

        potential_ratio = (
            1.0 if required <= 0 else min(1.0, effective_level / required)
        )
        verified_ratio = (
            1.0 if required <= 0 else min(1.0, verified_level / required)
        )
        if topic is None or topic_status not in ("canonical", "provisional"):
            unmatched_count += 1
            calculations.append(
                _Calculation(
                    skill=skill,
                    item=item,
                    potential_ratio=0.0,
                    verified_ratio=0.0,
                    topic_status=topic_status,
                    group_key=_group_key(skill),
                )
            )
            continue
        calculations.append(
            _Calculation(
                skill=skill,
                item=item,
                potential_ratio=potential_ratio,
                verified_ratio=verified_ratio,
                topic_status=topic_status,
                group_key=_group_key(skill),
            )
        )
        if topic_status == "provisional":
            provisional_count += 1
            provisional_weight += skill.weight

    grouped: dict[str, list[_Calculation]] = {}
    for calculation in calculations:
        grouped.setdefault(calculation.group_key, []).append(calculation)

    groups: list[_GroupDetail] = []
    for group in grouped.values():
        detail = _group_detail(group)
        groups.append(detail)
        if detail.critical and not detail.potential_satisfied:
            critical_gap_count += 1

    total_weight = sum(detail.weight for detail in groups)
    potential_done = sum(detail.weight * detail.potential_ratio for detail in groups)
    verified_done = sum(detail.weight * detail.verified_ratio for detail in groups)
    coverage_all = potential_done / total_weight if total_weight > 0 else (1.0 if not skills else 0.0)
    verified_coverage = (
        verified_done / total_weight if total_weight > 0 else (1.0 if not skills else 0.0)
    )

    canonical_weight = sum(
        detail.weight
        for detail in groups
        if all(calc.topic_status == "canonical" for calc in detail.calcs)
    )
    canonical_done = sum(
        detail.weight * detail.potential_ratio
        for detail in groups
        if all(calc.topic_status == "canonical" for calc in detail.calcs)
    )
    confirmed_readiness = (
        round(canonical_done / canonical_weight, 3) if canonical_weight > 0 else None
    )

    critical_metric_weight = sum(detail.weight for detail in groups if detail.critical)
    critical_done = sum(
        detail.weight * (1.0 if detail.potential_satisfied else 0.0)
        for detail in groups
        if detail.critical
    )
    critical_verified_done = sum(
        detail.weight * (1.0 if detail.verified_satisfied else 0.0)
        for detail in groups
        if detail.critical
    )
    critical_readiness = (
        round(critical_done / critical_metric_weight, 3)
        if critical_metric_weight > 0
        else None
    )
    critical_verified = (
        round(critical_verified_done / critical_metric_weight, 3)
        if critical_metric_weight > 0
        else None
    )
    critical_gate = _critical_gate(critical_readiness)
    verified_gate = _critical_gate(critical_verified)
    readiness = round(coverage_all * critical_gate, 3)
    verified_readiness = round(verified_coverage * verified_gate, 3)

    evidence_weight = sum(
        detail.weight
        for detail in groups
        if any(calc.item.verified_level > 0 for calc in detail.calcs)
    )
    evidence_coverage = evidence_weight / total_weight if total_weight > 0 else 1.0
    confidence = (
        round(sum(confidence_values) / len(confidence_values), 3)
        if confidence_values
        else 0.0
    )
    margin = round(0.03 + 0.12 * (1.0 - confidence), 3)
    readiness_low = round(max(0.0, readiness - margin), 3)
    readiness_high = round(min(1.0, readiness + margin), 3)
    average_gap = (
        round(weighted_gap_total / weighted_gap_weight, 1) if weighted_gap_weight > 0 else 0.0
    )
    band, band_reason = readiness_band(
        verified_readiness,
        critical_verified,
        readiness,
        evidence_coverage,
    )

    covered_ids: set[int] = set()
    for detail in groups:
        if detail.logic == "OR" and detail.potential_satisfied:
            covered_ids.update(
                id(calc.item)
                for calc in detail.calcs
                if not calc.item.satisfied
            )
    if covered_ids:
        items = [
            replace(item, covered_by_alternative=True) if id(item) in covered_ids else item
            for item in items
        ]

    blockers = _blockers(groups)
    confirmation_queue = _confirmation_queue(
        groups,
        total_weight,
        verified_readiness,
        critical_verified,
    )

    return GapReport(
        vacancy_id=vacancy.id,
        vacancy_title=vacancy.title,
        items=tuple(items),
        overall_readiness=round(coverage_all, 3),
        coverage_all=round(coverage_all, 3),
        confirmed_readiness=confirmed_readiness,
        critical_readiness=critical_readiness,
        satisfied_count=sum(1 for detail in groups if detail.potential_satisfied),
        requirements_count=len(groups),
        average_gap=average_gap,
        recommendations=_recommendations(items),
        provisional_count=provisional_count,
        provisional_weight=round(provisional_weight, 3),
        confirmed_weight=round(canonical_weight, 3),
        critical_count=critical_count,
        critical_weight=round(critical_weight, 3),
        critical_gap_count=critical_gap_count,
        unmatched_count=unmatched_count,
        readiness=readiness,
        readiness_low=readiness_low,
        readiness_high=readiness_high,
        critical_gate=critical_gate,
        confidence=confidence,
        potential_readiness=round(coverage_all, 3),
        verified_readiness=verified_readiness,
        critical_verified=critical_verified,
        evidence_coverage=round(evidence_coverage, 3),
        band=band,
        band_reason=band_reason,
        blockers=blockers,
        confirmation_queue=confirmation_queue,
    )


def _group_key(skill: VacancySkill) -> str:
    """Ключ требования: группа AND/OR или отдельный навык."""
    logic = skill.requirement_logic or "SINGLE"
    if skill.requirement_group and logic in ("AND", "OR"):
        return f"group:{skill.requirement_group}"
    return f"skill:{skill.id}"


def _group_detail(group: list[_Calculation]) -> _GroupDetail:
    """Сворачивает навыки группы в одно требование."""
    logic = group[0].skill.requirement_logic or "SINGLE"
    if logic == "OR":
        potential_ratio = max(calc.potential_ratio for calc in group)
        verified_ratio = max(calc.verified_ratio for calc in group)
        weight = max(calc.item.weight for calc in group)
        potential_satisfied = any(calc.item.satisfied for calc in group)
        verified_satisfied = any(calc.item.verified_satisfied for calc in group)
        verified_gap = min(calc.item.verified_gap for calc in group)
    elif logic == "AND":
        potential_ratio = min(calc.potential_ratio for calc in group)
        verified_ratio = min(calc.verified_ratio for calc in group)
        weight = sum(calc.item.weight for calc in group)
        potential_satisfied = all(calc.item.satisfied for calc in group)
        verified_satisfied = all(calc.item.verified_satisfied for calc in group)
        verified_gap = max(calc.item.verified_gap for calc in group)
    else:
        potential_ratio = group[0].potential_ratio
        verified_ratio = group[0].verified_ratio
        weight = group[0].item.weight
        potential_satisfied = group[0].item.satisfied
        verified_satisfied = group[0].item.verified_satisfied
        verified_gap = group[0].item.verified_gap

    representative = max(group, key=lambda calc: calc.item.verified_gap).item
    return _GroupDetail(
        calcs=tuple(group),
        weight=weight,
        logic=logic,
        critical=any(calc.item.criticality == "must_have" for calc in group),
        potential_ratio=potential_ratio,
        verified_ratio=verified_ratio,
        potential_satisfied=potential_satisfied,
        verified_satisfied=verified_satisfied,
        verified_gap=verified_gap,
        representative=representative,
    )


def _critical_gate(critical_readiness: float | None) -> float:
    """Критический гейт: обязательные требования режут общий процент."""
    if critical_readiness is None or critical_readiness >= 1.0:
        return 1.0
    return round(0.7 + 0.3 * critical_readiness, 3)


def _blockers(groups: list[_GroupDetail]) -> tuple[GapBlocker, ...]:
    """Обязательные требования, не закрытые подтверждёнными навыками."""
    blockers = [
        GapBlocker(
            skill_name=detail.representative.skill_name,
            topic_key=detail.representative.topic_key,
            topic_name=detail.representative.topic_name,
            required_level=detail.representative.required_level,
            verified_level=detail.representative.verified_level,
            gap=detail.verified_gap,
            weight=detail.weight,
            criticality="must_have",
        )
        for detail in groups
        if detail.critical and not detail.verified_satisfied
    ]
    blockers.sort(key=lambda item: (item.weight * item.gap, item.gap), reverse=True)
    return tuple(blockers[:5])


def _confirmation_queue(
    groups: list[_GroupDetail],
    total_weight: float,
    base_readiness: float,
    base_critical: float | None,
) -> tuple[GapConfirmation, ...]:
    """Считает, какие подтверждения сильнее всего уточнят готовность."""
    if total_weight <= 0:
        return ()
    candidates: list[GapConfirmation] = []
    seen: set[str] = set()
    for detail in groups:
        for calc in detail.calcs:
            item = calc.item
            key = item.topic_key or item.skill_name
            if key in seen or item.required_level <= 0:
                continue
            if item.verified_level >= item.required_level:
                continue
            target = max(item.required_level, item.self_level)
            simulated_readiness, _ = _simulate_verified(
                groups,
                total_weight,
                {id(calc.item): target},
            )
            gain = max(0.0, simulated_readiness - base_readiness)
            if gain <= 0:
                continue
            seen.add(key)
            if item.self_level >= item.required_level:
                reason = "Резюме заявляет достаточный уровень, тест закрепит его."
            elif item.self_level > 0:
                reason = (
                    f"Резюме: {item.self_level} из {item.required_level}. "
                    "Подтверждение покажет реальный уровень."
                )
            else:
                reason = "Навык требуется вакансией, но подтверждений нет."
            candidates.append(
                GapConfirmation(
                    skill_name=item.skill_name,
                    topic_key=item.topic_key,
                    topic_name=item.topic_name,
                    required_level=item.required_level,
                    self_level=item.self_level,
                    verified_level=item.verified_level,
                    criticality=item.criticality,
                    potential_gain=round(gain, 3),
                    reason=reason,
                )
            )
    candidates.sort(
        key=lambda item: (
            item.criticality == "must_have",
            item.potential_gain,
            item.required_level - item.verified_level,
        ),
        reverse=True,
    )
    must_have = [item for item in candidates if item.criticality == "must_have"]
    nice = [item for item in candidates if item.criticality != "must_have"]
    limit = max(10, len(must_have))
    return tuple((must_have + nice)[:limit])


def _simulate_verified(
    groups: list[_GroupDetail],
    total_weight: float,
    overrides: dict[int, int],
) -> tuple[float, float | None]:
    """Пересчитывает подтверждённую готовность с подменой уровней."""
    done = 0.0
    critical_weight = 0.0
    critical_done = 0.0
    for detail in groups:
        ratios: list[float] = []
        satisfied: list[bool] = []
        for calc in detail.calcs:
            level = overrides.get(id(calc.item), calc.item.verified_level)
            required = calc.item.required_level
            ratios.append(1.0 if required <= 0 else min(1.0, level / required))
            satisfied.append(level >= required)
        if detail.logic == "OR":
            ratio = max(ratios)
            group_satisfied = any(satisfied)
        elif detail.logic == "AND":
            ratio = min(ratios)
            group_satisfied = all(satisfied)
        else:
            ratio = ratios[0]
            group_satisfied = satisfied[0]
        done += detail.weight * ratio
        if detail.critical:
            critical_weight += detail.weight
            critical_done += detail.weight * (1.0 if group_satisfied else 0.0)
    readiness = done / total_weight
    critical = critical_done / critical_weight if critical_weight > 0 else None
    return round(readiness * _critical_gate(critical), 3), critical


def _recommendations(items: list[GapItem], limit: int = 5) -> tuple[GapRecommendation, ...]:
    """Возвращает до `limit` тем, которые нужно подтянуть в первую очередь."""
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
        criticality = "обязательное" if item.criticality == "must_have" else "желательное"
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
                    f"{criticality.capitalize()} требование, вес {item.weight:.2f}: "
                    f"не хватает {item.gap} из {item.required_level}"
                ),
            )
        )
        if len(result) >= limit:
            break
    return tuple(result)
