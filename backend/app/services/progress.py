"""Агрегаты для дашборда и прогресса подготовки."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    InterviewSession,
    InterviewTurn,
    LearningPlan,
    PlanItem,
    Resume,
    Topic,
    TopicTestResult,
    UserSkillState,
    Vacancy,
)
from app.schemas.analysis import GapBlockerRead, GapConfirmationRead
from app.schemas.progress import (
    DashboardActiveInterviewRead,
    DashboardActivityRead,
    DashboardFocusTopicRead,
    DashboardHistoryRead,
    DashboardInterviewRead,
    DashboardPlanRead,
    DashboardProfileRead,
    DashboardRead,
    DashboardReviewTopicRead,
    DashboardTestsRead,
    DashboardVacancyRead,
    PlanProgressItemRead,
    PlanProgressRead,
)
from app.services.gaps import compute_gaps
from app.services.interview import list_interviews
from app.services.learning_topics import NON_LEARNING_TOPIC_KEYS
from app.services.plans import PlanNotFoundError

TEST_PASS_RATIO = 0.6


async def build_dashboard(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    vacancy_id: uuid.UUID | None = None,
) -> DashboardRead:
    """Собирает снимок прогресса пользователя."""
    vacancy = await _select_vacancy(session, user_id, vacancy_id)
    profile = await _profile_summary(session, user_id)
    tests = await _tests_summary(session, user_id)
    interviews = [
        item
        for item in await list_interviews(session, user_id)
        if item.status == "completed" and item.score is not None
    ]

    last_interview = None
    if interviews:
        latest = interviews[0]
        previous = next(
            (
                item
                for item in interviews[1:]
                if item.vacancy_id == latest.vacancy_id
            ),
            None,
        )
        delta = (
            round(latest.score - previous.score, 1)
            if previous is not None
            and latest.score is not None
            and previous.score is not None
            else None
        )
        last_interview = DashboardInterviewRead(
            id=latest.id,
            vacancy_id=latest.vacancy_id,
            vacancy_title=latest.vacancy_title,
            score=latest.score,
            level=latest.level,
            finished_at=latest.finished_at,
            delta=delta,
        )

    vacancy_snapshot = None
    if vacancy is not None:
        gaps = await compute_gaps(session, user_id, vacancy.id)
        vacancy_snapshot = DashboardVacancyRead(
            id=vacancy.id,
            title=vacancy.title,
            company=vacancy.company,
            coverage=gaps.coverage_all,
            critical_readiness=gaps.critical_readiness,
            average_gap=gaps.average_gap,
            readiness=gaps.readiness,
            readiness_low=gaps.readiness_low,
            readiness_high=gaps.readiness_high,
            critical_gate=gaps.critical_gate,
            requirements_count=gaps.requirements_count,
            satisfied_count=gaps.satisfied_count,
            critical_gap_count=gaps.critical_gap_count,
            verified_readiness=gaps.verified_readiness,
            critical_verified=gaps.critical_verified,
            evidence_coverage=gaps.evidence_coverage,
            band=gaps.band,
            band_reason=gaps.band_reason,
            blockers=[
                GapBlockerRead(
                    skill_name=item.skill_name,
                    topic_key=item.topic_key,
                    topic_name=item.topic_name,
                    required_level=item.required_level,
                    verified_level=item.verified_level,
                    gap=item.gap,
                    weight=item.weight,
                    criticality=item.criticality,
                )
                for item in gaps.blockers
            ],
            confirmation_queue=[
                GapConfirmationRead(
                    skill_name=item.skill_name,
                    topic_key=item.topic_key,
                    topic_name=item.topic_name,
                    required_level=item.required_level,
                    self_level=item.self_level,
                    verified_level=item.verified_level,
                    criticality=item.criticality,
                    potential_gain=item.potential_gain,
                    reason=item.reason,
                )
                for item in gaps.confirmation_queue
            ],
            focus_topics=[
                DashboardFocusTopicRead(
                    topic_key=item.topic_key,
                    topic_name=item.topic_name,
                    skill_name=item.skill_name,
                    current_level=item.user_level,
                    required_level=item.required_level,
                    gap=item.gap,
                    criticality=item.criticality,
                )
                for item in gaps.recommendations[:3]
            ],
        )

    plan = await _active_plan(session, user_id, vacancy)
    plan_snapshot = None
    if plan is not None:
        progress = await build_plan_progress(session, user_id, plan.id)
        plan_snapshot = DashboardPlanRead(
            id=plan.id,
            title=plan.title,
            kind="vacancy" if plan.vacancy_id is not None else "general",
            topic_count=progress.topics_total,
            progress=progress.progress,
            completed_count=progress.completed_count,
            remaining_count=progress.remaining_count,
            tests_completed=progress.tests_completed,
            tests_passed=progress.tests_passed,
            average_score=progress.average_score,
            attempts_count=progress.attempts_count,
        )

    active_plans = (
        await session.scalar(
            select(func.count())
            .select_from(LearningPlan)
            .where(
                LearningPlan.user_id == user_id,
                LearningPlan.status == "active",
            )
        )
    ) or 0

    active = await _active_interview(session, user_id, vacancy)
    active_snapshot = None
    if active is not None:
        active_vacancy = (
            await session.get(Vacancy, active.vacancy_id)
            if active.vacancy_id is not None
            else None
        )
        active_answered = (
            await session.scalar(
                select(func.count())
                .select_from(InterviewTurn)
                .where(
                    InterviewTurn.session_id == active.id,
                    InterviewTurn.status == "answered",
                )
            )
        ) or 0
        active_snapshot = DashboardActiveInterviewRead(
            id=active.id,
            vacancy_id=active.vacancy_id,
            vacancy_title=active_vacancy.title if active_vacancy is not None else None,
            answered_count=active_answered,
            max_questions=active.max_questions,
            started_at=active.started_at,
        )

    review_topics = [
        DashboardReviewTopicRead(
            topic_key=topic.key,
            topic_name=topic.name,
            current_level=state.proficiency,
            review_due_at=state.review_due_at,
            review_interval_days=state.review_interval_days,
        )
        for state, topic in (
            await session.execute(
                select(UserSkillState, Topic)
                .join(Topic, Topic.id == UserSkillState.topic_id)
                .where(
                    UserSkillState.user_id == user_id,
                    UserSkillState.review_due_at.is_not(None),
                    UserSkillState.review_due_at <= datetime.now(UTC),
                )
                .order_by(UserSkillState.review_due_at)
                .limit(5)
            )
        ).all()
    ]

    return DashboardRead(
        profile=profile,
        vacancy=vacancy_snapshot,
        last_interview=last_interview,
        active_interview=active_snapshot,
        review_topics=review_topics,
        interview_history=[
            DashboardHistoryRead(
                id=item.id,
                vacancy_title=item.vacancy_title,
                score=item.score,
                level=item.level,
                finished_at=item.finished_at,
            )
            for item in interviews[:5]
        ],
        plan=plan_snapshot,
        tests=tests,
        activity=DashboardActivityRead(
            interviews_completed=len(interviews),
            tests_completed=tests.completed_count,
            active_plans=active_plans,
        ),
    )


async def build_plan_progress(
    session: AsyncSession,
    user_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> PlanProgressRead:
    """Считает прогресс плана по лучшим результатам тестов.

    Каждая тема даёт равную долю 1/N. Внутри темы балл взвешен сложностью
    вопросов ещё на этапе проверки. Резюме и интервью в прогресс не входят:
    они нужны для плана и готовности к вакансии, но не подтверждают выполнение.
    """
    plan = await session.get(LearningPlan, plan_id)
    if plan is None or plan.user_id != user_id or plan.status == "archived":
        raise PlanNotFoundError("План не найден")

    rows = (
        await session.execute(
            select(PlanItem, Topic)
            .join(Topic, Topic.id == PlanItem.topic_id)
            .where(PlanItem.plan_id == plan.id)
            .order_by(PlanItem.position)
        )
    ).all()
    topic_ids = [topic.id for _, topic in rows]
    results_by_topic: dict[uuid.UUID, list[TopicTestResult]] = {}
    if topic_ids:
        results = (
            await session.scalars(
                select(TopicTestResult)
                .where(
                    TopicTestResult.user_id == user_id,
                    TopicTestResult.topic_id.in_(topic_ids),
                )
                .order_by(TopicTestResult.completed_at)
            )
        ).all()
        for result in results:
            results_by_topic.setdefault(result.topic_id, []).append(result)

    items: list[PlanProgressItemRead] = []
    next_topic_key: str | None = None
    next_topic_name: str | None = None
    for item, topic in rows:
        attempts = results_by_topic.get(topic.id, [])
        best = (
            max(attempts, key=lambda result: (result.score, result.level))
            if attempts
            else None
        )
        score = best.score if best is not None else 0.0
        test_level = best.level if best is not None else 0
        target = item.target_level or 80
        target_ratio = min(1.0, max(0.0, target / 100))
        completed = best is not None and score >= target_ratio
        if best is None:
            status = "not_tested"
            if next_topic_key is None:
                next_topic_key = topic.key
                next_topic_name = topic.name
        elif completed:
            status = "confirmed"
        else:
            status = "partial"
        items.append(
            PlanProgressItemRead(
                topic_id=topic.id,
                topic_key=topic.key,
                topic_name=topic.name,
                current_level=test_level,
                target_level=target,
                progress=round(score, 3),
                completed=completed,
                test_level=test_level if best is not None else None,
                test_score=round(score, 3) if best is not None else None,
                interview_score=None,
                status=status,
                attempts_count=len(attempts),
                last_tested_at=best.completed_at if best is not None else None,
            )
        )

    progress_value = (
        round(sum(item.progress for item in items) / len(items), 3)
        if items
        else 0.0
    )
    completed = sum(1 for item in items if item.completed)
    attempted = [item for item in items if item.attempts_count > 0]
    average_score = (
        round(sum(item.progress for item in attempted) / len(attempted), 3)
        if attempted
        else None
    )
    return PlanProgressRead(
        plan_id=plan.id,
        progress=progress_value,
        topics_total=len(items),
        completed_count=completed,
        remaining_count=len(items) - completed,
        tests_completed=len(attempted),
        tests_passed=sum(
            1 for item in attempted if item.progress >= TEST_PASS_RATIO
        ),
        average_score=average_score,
        attempts_count=sum(item.attempts_count for item in items),
        next_topic_key=next_topic_key,
        next_topic_name=next_topic_name,
        items=items,
    )


async def _select_vacancy(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy_id: uuid.UUID | None,
) -> Vacancy | None:
    """Выбранная вакансия или последняя загруженная."""
    if vacancy_id is not None:
        vacancy = await session.get(Vacancy, vacancy_id)
        if vacancy is None or vacancy.user_id != user_id:
            return None
        return vacancy
    return await session.scalar(
        select(Vacancy)
        .where(Vacancy.user_id == user_id)
        .order_by(Vacancy.created_at.desc())
        .limit(1)
    )


async def _profile_summary(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> DashboardProfileRead:
    """Количество тем и подтверждённых тем."""
    topics_count = (
        await session.scalar(
            select(func.count())
            .select_from(UserSkillState)
            .join(Topic, Topic.id == UserSkillState.topic_id)
            .where(
                UserSkillState.user_id == user_id,
                Topic.key.not_in(NON_LEARNING_TOPIC_KEYS),
            )
        )
    ) or 0
    confirmed = (
        await session.scalar(
            select(func.count())
            .select_from(UserSkillState)
            .join(Topic, Topic.id == UserSkillState.topic_id)
            .where(
                UserSkillState.user_id == user_id,
                UserSkillState.verified_level.is_not(None),
                Topic.status == "canonical",
                Topic.key.not_in(NON_LEARNING_TOPIC_KEYS),
            )
        )
    ) or 0
    return DashboardProfileRead(
        topics_count=topics_count,
        confirmed_count=confirmed,
    )


async def _tests_summary(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> DashboardTestsRead:
    """Количество тем с тестами и средний лучший уровень."""
    best = (
        select(
            TopicTestResult.topic_id,
            func.max(TopicTestResult.level).label("level"),
        )
        .where(TopicTestResult.user_id == user_id)
        .group_by(TopicTestResult.topic_id)
        .subquery()
    )
    count, average = (
        await session.execute(select(func.count(), func.avg(best.c.level)))
    ).one()
    return DashboardTestsRead(
        completed_count=count or 0,
        average_level=round(float(average), 1) if average is not None else None,
    )


async def _active_plan(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy: Vacancy | None,
) -> LearningPlan | None:
    """Активный план для текущего резюме и вакансии."""
    active_resume_id = await session.scalar(
        select(Resume.id).where(Resume.user_id == user_id, Resume.is_active.is_(True))
    )
    if active_resume_id is None:
        return None
    query = select(LearningPlan).where(
        LearningPlan.user_id == user_id,
        LearningPlan.status == "active",
        LearningPlan.resume_id == active_resume_id,
    )
    if vacancy is not None:
        query = query.where(LearningPlan.vacancy_id == vacancy.id)
    return await session.scalar(
        query.order_by(LearningPlan.created_at.desc()).limit(1)
    )


async def _active_interview(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy: Vacancy | None,
) -> InterviewSession | None:
    """Последнее незавершённое интервью по вакансии или любое."""
    query = select(InterviewSession).where(
        InterviewSession.user_id == user_id,
        InterviewSession.status == "in_progress",
    )
    if vacancy is not None:
        query = query.where(InterviewSession.vacancy_id == vacancy.id)
    return await session.scalar(
        query.order_by(InterviewSession.started_at.desc()).limit(1)
    )
