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
    Topic,
    TopicTestResult,
    UserSkillState,
    Vacancy,
)
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
            topic_count=progress.topics_total,
            progress=progress.progress,
            completed_count=progress.completed_count,
            remaining_count=progress.remaining_count,
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
    """Считает живой прогресс плана по текущему профилю и тестам."""
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
    states = {
        state.topic_id: state
        for state in (
            await session.scalars(
                select(UserSkillState).where(UserSkillState.user_id == user_id)
            )
        ).all()
    }
    test_levels = {
        topic_id: level
        for topic_id, level in (
            await session.execute(
                select(TopicTestResult.topic_id, TopicTestResult.level).where(
                    TopicTestResult.user_id == user_id
                )
            )
        ).all()
    }
    interview_scores = await _latest_topic_scores(
        session, user_id, plan.vacancy_id
    )

    items: list[PlanProgressItemRead] = []
    for item, topic in rows:
        state = states.get(topic.id)
        current = state.proficiency if state is not None else item.current_level
        target = item.target_level or 100
        progress = min(1.0, current / target) if target > 0 else 1.0
        items.append(
            PlanProgressItemRead(
                topic_id=topic.id,
                topic_key=topic.key,
                topic_name=topic.name,
                current_level=current,
                target_level=target,
                progress=round(progress, 3),
                completed=current >= target,
                test_level=test_levels.get(topic.id),
                interview_score=interview_scores.get(topic.id),
            )
        )

    progress_value = (
        round(sum(item.progress for item in items) / len(items), 3)
        if items
        else 0.0
    )
    completed = sum(1 for item in items if item.completed)
    return PlanProgressRead(
        plan_id=plan.id,
        progress=progress_value,
        topics_total=len(items),
        completed_count=completed,
        remaining_count=len(items) - completed,
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
    """Количество тестов и средний уровень."""
    count, average = (
        await session.execute(
            select(func.count(), func.avg(TopicTestResult.level)).where(
                TopicTestResult.user_id == user_id
            )
        )
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
    """Активный план для вакансии или последний активный."""
    query = select(LearningPlan).where(
        LearningPlan.user_id == user_id,
        LearningPlan.status == "active",
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


async def _latest_topic_scores(
    session: AsyncSession,
    user_id: uuid.UUID,
    vacancy_id: uuid.UUID | None,
) -> dict[uuid.UUID, float]:
    """Оценки тем из последнего завершённого интервью."""
    query = select(InterviewSession).where(
        InterviewSession.user_id == user_id,
        InterviewSession.status == "completed",
    )
    if vacancy_id is not None:
        query = query.where(InterviewSession.vacancy_id == vacancy_id)
    interview = await session.scalar(
        query.order_by(InterviewSession.finished_at.desc()).limit(1)
    )
    if interview is None:
        return {}
    rows = (
        await session.execute(
            select(InterviewTurn.topic_id, InterviewTurn.score).where(
                InterviewTurn.session_id == interview.id,
                InterviewTurn.status == "answered",
            )
        )
    ).all()
    return {
        topic_id: float(score)
        for topic_id, score in rows
        if score is not None
    }
