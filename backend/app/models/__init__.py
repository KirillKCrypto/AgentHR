"""ORM-модели AgentHR.

Модуль импортирует все модели, чтобы `Base.metadata` был полным —
это используется Alembic для autogenerate.
"""

from app.db.base import Base
from app.models.agent_action import AgentAction
from app.models.ontology_review import OntologyReviewAction
from app.models.resume import Resume, ResumeSkill
from app.models.topic import Topic, TopicAlias, TopicCandidate, TopicPrerequisite
from app.models.user import User
from app.models.user_skill_state import UserSkillState
from app.models.vacancy import Vacancy, VacancySkill

__all__ = [
    "AgentAction",
    "Base",
    "OntologyReviewAction",
    "Resume",
    "ResumeSkill",
    "Topic",
    "TopicAlias",
    "TopicCandidate",
    "TopicPrerequisite",
    "User",
    "UserSkillState",
    "Vacancy",
    "VacancySkill",
]
