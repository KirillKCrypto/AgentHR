"""Преобразование доменных объектов сервисного слоя в Pydantic-схемы API."""

from datetime import UTC, datetime

from app.models import Resume, Vacancy
from app.schemas.analysis import (
    GapAnalysisRead,
    GapItemRead,
    GapRecommendationRead,
    ProfileRead,
    ProfileTopicRead,
    ResumeRead,
    SkillRead,
    TopicBrief,
    UnmatchedSkillRead,
    VacancyRead,
)
from app.schemas.interview import (
    InterviewRead,
    InterviewReportRead,
    InterviewReportTopicRead,
    InterviewSummaryRead,
    InterviewTurnRead,
)
from app.schemas.plan import PlanItemRead, PlanRead, PlanSummaryRead
from app.services.gaps import GapReport
from app.services.interview import (
    InterviewReport,
    InterviewSnapshot,
    InterviewSummary,
    InterviewTurnData,
    ReportTopic,
)
from app.services.plans import PlanSnapshot, PlanSummary
from app.services.profile import (
    ProfileSnapshot,
    SkillEntry,
    TopicBriefData,
)


def vacancy_read(vacancy: Vacancy, skills: tuple[SkillEntry, ...]) -> VacancyRead:
    """Вакансия с навыками для ответа API."""
    return VacancyRead(
        id=vacancy.id,
        user_id=vacancy.user_id,
        title=vacancy.title,
        company=vacancy.company,
        level=vacancy.level,
        raw_text=vacancy.raw_text,
        created_at=vacancy.created_at,
        skills=skills_read(skills),
    )


def resume_read(resume: Resume, skills: tuple[SkillEntry, ...]) -> ResumeRead:
    """Резюме с навыками для ответа API."""
    return ResumeRead(
        id=resume.id,
        user_id=resume.user_id,
        title=resume.title,
        raw_text=resume.raw_text,
        created_at=resume.created_at,
        skills=skills_read(skills),
    )


def topic_brief(topic: TopicBriefData | None) -> TopicBrief | None:
    """Тема онтологии для ответа API."""
    if topic is None:
        return None
    return TopicBrief(
        id=topic.id,
        key=topic.key,
        name=topic.name,
        category=topic.category,
        status=topic.status,
    )


def skill_read(entry: SkillEntry) -> SkillRead:
    """Навык документа для ответа API."""
    return SkillRead(
        id=entry.id,
        raw_name=entry.raw_name,
        level=entry.level,
        weight=entry.weight,
        confidence=entry.confidence,
        evidence=entry.evidence,
        match_method=entry.match_method,
        topic=topic_brief(entry.topic),
        requirement_group=entry.requirement_group,
        requirement_logic=entry.requirement_logic,
        criticality=entry.criticality,
    )


def skills_read(entries: tuple[SkillEntry, ...]) -> list[SkillRead]:
    """Список навыков документа."""
    return [skill_read(entry) for entry in entries]


def profile_read(snapshot: ProfileSnapshot) -> ProfileRead:
    """Профиль знаний для ответа API."""
    return ProfileRead(
        user_id=snapshot.user_id,
        topics=[
            ProfileTopicRead(
                topic_id=topic.topic_id,
                topic_key=topic.topic_key,
                topic_name=topic.topic_name,
                category=topic.category,
                proficiency=topic.proficiency,
                confidence=topic.confidence,
                source=topic.source,
                evidence_type=topic.evidence_type,
                verified_level=topic.verified_level,
                last_assessed=topic.last_assessed,
                status=topic.status,
            )
            for topic in snapshot.topics
        ],
        unmatched_skills=[
            UnmatchedSkillRead(
                raw_name=skill.raw_name,
                level=skill.level,
                confidence=skill.confidence,
                evidence=skill.evidence,
                match_method=skill.match_method,
            )
            for skill in snapshot.unmatched_skills
        ],
    )


def plan_read(plan: PlanSnapshot) -> PlanRead:
    """План подготовки для ответа API."""
    return PlanRead(
        id=plan.id,
        user_id=plan.user_id,
        vacancy_id=plan.vacancy_id,
        vacancy_title=plan.vacancy_title,
        title=plan.title,
        status=plan.status,
        created_at=None,
        reused=plan.reused,
        items=[
            PlanItemRead(
                topic_id=item.topic_id,
                topic_key=item.topic_key,
                topic_name=item.topic_name,
                category=item.category,
                current_level=item.current_level,
                target_level=item.target_level,
                confidence=item.confidence,
                priority=item.priority,
                reason=item.reason,
                question_count=item.question_count,
            )
            for item in plan.items
        ],
    )


def plan_summary_read(plan: PlanSummary) -> PlanSummaryRead:
    """Краткая карточка плана."""
    return PlanSummaryRead(
        id=plan.id,
        title=plan.title,
        status=plan.status,
        vacancy_id=plan.vacancy_id,
        topic_count=plan.topic_count,
    )


def interview_turn_read(turn: InterviewTurnData) -> InterviewTurnRead:
    """Вопрос интервью для ответа API."""
    return InterviewTurnRead(
        id=turn.id,
        position=turn.position,
        topic_id=turn.topic_id,
        topic_key=turn.topic_key,
        topic_name=turn.topic_name,
        question_text=turn.question_text,
        context=turn.context,
        kind=turn.kind,
        parent_turn_id=turn.parent_turn_id,
        deadline_at=turn.deadline_at,
        answer_mode=turn.answer_mode,
        difficulty=turn.difficulty,
        status=turn.status,
        answer_text=turn.answer_text,
        score=turn.score,
        verdict=turn.verdict,
        feedback=turn.feedback,
        covered_points=list(turn.covered_points),
        missed_points=list(turn.missed_points),
        score_breakdown=turn.score_breakdown,
        answered_at=turn.answered_at,
    )


def interview_read(snapshot: InterviewSnapshot) -> InterviewRead:
    """Сессия интервью для ответа API."""
    return InterviewRead(
        id=snapshot.id,
        user_id=snapshot.user_id,
        plan_id=snapshot.plan_id,
        vacancy_id=snapshot.vacancy_id,
        vacancy_title=snapshot.vacancy_title,
        title=snapshot.title,
        status=snapshot.status,
        score=snapshot.score,
        level=snapshot.level,
        question_count=snapshot.question_count,
        max_questions=snapshot.max_questions,
        answer_seconds=snapshot.answer_seconds,
        answered_count=snapshot.answered_count,
        created_at=snapshot.created_at,
        started_at=snapshot.started_at,
        finished_at=snapshot.finished_at,
        server_time=datetime.now(UTC),
        reused=snapshot.reused,
        turns=[interview_turn_read(turn) for turn in snapshot.turns],
    )


def interview_summary_read(summary: InterviewSummary) -> InterviewSummaryRead:
    """Краткая карточка интервью."""
    return InterviewSummaryRead(
        id=summary.id,
        title=summary.title,
        status=summary.status,
        level=summary.level,
        vacancy_id=summary.vacancy_id,
        vacancy_title=summary.vacancy_title,
        score=summary.score,
        question_count=summary.question_count,
        max_questions=summary.max_questions,
        answered_count=summary.answered_count,
        created_at=summary.created_at,
        finished_at=summary.finished_at,
    )


def interview_report_read(report: InterviewReport) -> InterviewReportRead:
    """Итоги интервью для ответа API."""
    return InterviewReportRead(
        interview_id=report.interview_id,
        status=report.status,
        score=report.score,
        level=report.level,
        vacancy_id=report.vacancy_id,
        vacancy_title=report.vacancy_title,
        finished_at=report.finished_at,
        question_count=report.question_count,
        answered_count=report.answered_count,
        dimensions=report.dimensions,
        previous_score=report.previous_score,
        delta=report.delta,
        strengths=[_report_topic_read(item) for item in report.strengths],
        improvements=[_report_topic_read(item) for item in report.improvements],
        untouched=[_report_topic_read(item) for item in report.untouched],
    )


def _report_topic_read(topic: ReportTopic) -> InterviewReportTopicRead:
    """Тема отчёта интервью."""
    return InterviewReportTopicRead(
        topic_key=topic.topic_key,
        topic_name=topic.topic_name,
        score=topic.score,
        missed_points=list(topic.missed_points),
    )


def gap_analysis_read(report: GapReport) -> GapAnalysisRead:
    """Gap-анализ для ответа API."""
    return GapAnalysisRead(
        vacancy_id=report.vacancy_id,
        vacancy_title=report.vacancy_title,
        items=[
            GapItemRead(
                skill_name=item.skill_name,
                required_level=item.required_level,
                user_level=item.user_level,
                gap=item.gap,
                satisfied=item.satisfied,
                weight=item.weight,
                topic_key=item.topic_key,
                topic_name=item.topic_name,
                topic_status=item.topic_status,
                requirement_group=item.requirement_group,
                requirement_logic=item.requirement_logic,
                criticality=item.criticality,
                covered_by_alternative=item.covered_by_alternative,
            )
            for item in report.items
        ],
        recommendations=[
            GapRecommendationRead(
                topic_key=item.topic_key,
                topic_name=item.topic_name,
                skill_name=item.skill_name,
                required_level=item.required_level,
                user_level=item.user_level,
                gap=item.gap,
                priority=item.priority,
                criticality=item.criticality,
                reason=item.reason,
            )
            for item in report.recommendations
        ],
        overall_readiness=report.overall_readiness,
        coverage_all=report.coverage_all,
        confirmed_readiness=report.confirmed_readiness,
        critical_readiness=report.critical_readiness,
        satisfied_count=report.satisfied_count,
        requirements_count=report.requirements_count,
        average_gap=report.average_gap,
        provisional_count=report.provisional_count,
        provisional_weight=report.provisional_weight,
        confirmed_weight=report.confirmed_weight,
        critical_count=report.critical_count,
        critical_weight=report.critical_weight,
        critical_gap_count=report.critical_gap_count,
        unmatched_count=report.unmatched_count,
        readiness=report.readiness,
        readiness_low=report.readiness_low,
        readiness_high=report.readiness_high,
        critical_gate=report.critical_gate,
        confidence=report.confidence,
    )
