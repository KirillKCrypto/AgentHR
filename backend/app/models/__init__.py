"""ORM-модели AgentHR.

Модуль импортирует все модели, чтобы `Base.metadata` был полным —
это использует Alembic для autogenerate.
"""

from app.db.base import Base
from app.models.agent_action import AgentAction
from app.models.user import User

__all__ = ["AgentAction", "Base", "User"]
