"""Преобразование доменных объектов сервисного слоя в Pydantic-схемы API."""

from app.models import Resume, Vacancy
from app.schemas.analysis import (
    GapAnalysisRead,
    GapItemRead,
    ProfileRead,
    ProfileTopicRead,
    ResumeRead,
    SkillRead,
    TopicBrief,
    UnmatchedSkillRead,
    VacancyRead,
)
from app.services.profile import (
    GapReport,
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
            )
            for item in report.items
        ],
        overall_readiness=report.overall_readiness,
        coverage_all=report.coverage_all,
        confirmed_readiness=report.confirmed_readiness,
        provisional_count=report.provisional_count,
        provisional_weight=report.provisional_weight,
        confirmed_weight=report.confirmed_weight,
        unmatched_count=report.unmatched_count,
    )
