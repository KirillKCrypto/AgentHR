"""Извлечение требований вакансии и навыков резюме.

Сервисный слой: детерминированный сценарий «текст → структура» (решение команды,
см. decision log в `AGENTS.md`). Те же функции регистрируются как tools агента,
поэтому доступ LLM к данным остаётся только через инструменты.
"""

from dataclasses import dataclass
from typing import Any

from app.llm.base import ChatMessage, LLMProvider

VACANCY_SCHEMA_NAME = "vacancy_requirements"
RESUME_SCHEMA_NAME = "resume_skills"

VACANCY_SYSTEM_PROMPT = (
    "Ты — аналитик вакансий. Из текста вакансии извлеки требования к кандидату.\n"
    "Правила:\n"
    "- Называй навыки так, как они написаны в тексте: не переводи, не сокращай, "
    "не объединяй разные навыки.\n"
    "- required_level — ожидаемый уровень владения навыком, целое число 0..100 "
    "(0 — не требуется, 40 — базовый, 70 — уверенный, 90 — экспертный).\n"
    "- weight — важность навыка для этой вакансии, число 0..1.\n"
    "- evidence — короткая цитата из текста вакансии, подтверждающая навык.\n"
    "- confidence — уверенность в извлечении, число 0..1.\n"
    '- group — необязательный идентификатор группы требований (например, "req_1"). '
    "Одинаковый group у нескольких навыков означает, что они связаны логикой.\n"
    "- logic — SINGLE для обычного требования, OR для альтернативы "
    '("R or Java", "Python или Go"), AND для конъюнкции '
    '("Docker and Kubernetes"). Если сомневаешься — SINGLE.\n'
    "Не выдумывай навыки, которых нет в тексте. Если вакансия не содержит требований — "
    "верни пустой список skills."
)

RESUME_SYSTEM_PROMPT = (
    "Ты — аналитик резюме. Из текста резюме извлеки навыки кандидата.\n"
    "Правила:\n"
    "- Называй навыки так, как они написаны в тексте: не переводи, не сокращай, "
    "не объединяй разные навыки.\n"
    "- proficiency — оценка владения навыком по тому, что описано в резюме, "
    "целое число 0..100 (20 — пробовал, 50 — уверенный базовый, 80 — сильный).\n"
    "- evidence — короткая цитата из резюме, подтверждающая навык.\n"
    "- confidence — уверенность в извлечении, число 0..1.\n"
    "Не выдумывай навыки, которых нет в тексте. Если навыков нет — верни пустой список skills."
)

_SKILL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "required_level", "weight", "evidence", "confidence"],
    "properties": {
        "name": {"type": "string"},
        "required_level": {"type": "integer", "minimum": 0, "maximum": 100},
        "weight": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "group": {"type": ["string", "null"], "description": "Идентификатор группы требований"},
        "logic": {
            "type": "string",
            "enum": ["SINGLE", "AND", "OR"],
            "description": "Логика группы требований",
        },
    },
}

VACANCY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "company", "level", "skills"],
    "properties": {
        "title": {"type": ["string", "null"]},
        "company": {"type": ["string", "null"]},
        "level": {"type": ["string", "null"], "description": "junior | middle | senior | lead"},
        "skills": {"type": "array", "items": _SKILL_SCHEMA},
    },
}

RESUME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["experience_years", "self_level", "skills"],
    "properties": {
        "experience_years": {"type": ["number", "null"]},
        "self_level": {"type": ["string", "null"]},
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "proficiency", "evidence", "confidence"],
                "properties": {
                    "name": {"type": "string"},
                    "proficiency": {"type": "integer", "minimum": 0, "maximum": 100},
                    "evidence": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
    },
}


class AnalysisError(Exception):
    """Ошибка слоя анализа (пустой текст, неожиданный ответ модели)."""


@dataclass(frozen=True)
class ExtractedSkill:
    """Навык, извлечённый из текста."""

    name: str
    level: int
    weight: float = 1.0
    evidence: str | None = None
    confidence: float = 0.5
    group: str | None = None
    logic: str = "SINGLE"

    @property
    def is_named(self) -> bool:
        """Есть ли осмысленное название навыка."""
        return bool(self.name.strip())


@dataclass(frozen=True)
class VacancyRequirements:
    """Требования вакансии."""

    title: str | None = None
    company: str | None = None
    level: str | None = None
    skills: tuple[ExtractedSkill, ...] = ()


@dataclass(frozen=True)
class ResumeProfile:
    """Навыки и опыт из резюме."""

    experience_years: float | None = None
    self_level: str | None = None
    skills: tuple[ExtractedSkill, ...] = ()


async def extract_vacancy_requirements(provider: LLMProvider, text: str) -> VacancyRequirements:
    """Извлекает требования вакансии из её текста."""
    if not text or not text.strip():
        raise AnalysisError("Текст вакансии пуст")
    result = await provider.generate_structured(
        messages=[
            ChatMessage(role="system", content=VACANCY_SYSTEM_PROMPT),
            ChatMessage(role="user", content=text),
        ],
        schema=VACANCY_SCHEMA,
        schema_name=VACANCY_SCHEMA_NAME,
    )
    return _parse_vacancy(result.data)


async def extract_resume_skills(provider: LLMProvider, text: str) -> ResumeProfile:
    """Извлекает навыки и опыт из текста резюме."""
    if not text or not text.strip():
        raise AnalysisError("Текст резюме пуст")
    result = await provider.generate_structured(
        messages=[
            ChatMessage(role="system", content=RESUME_SYSTEM_PROMPT),
            ChatMessage(role="user", content=text),
        ],
        schema=RESUME_SCHEMA,
        schema_name=RESUME_SCHEMA_NAME,
    )
    return _parse_resume(result.data)


def _parse_vacancy(data: dict[str, Any]) -> VacancyRequirements:
    """Разбирает ответ модели в структуру требований."""
    skills = tuple(
        skill
        for skill in (
            _parse_skill(item, level_field="required_level") for item in _skill_items(data)
        )
        if skill.is_named
    )
    return VacancyRequirements(
        title=_optional_str(data.get("title")),
        company=_optional_str(data.get("company")),
        level=_optional_str(data.get("level")),
        skills=skills,
    )


def _parse_resume(data: dict[str, Any]) -> ResumeProfile:
    """Разбирает ответ модели в структуру профиля из резюме."""
    skills = tuple(
        skill
        for skill in (_parse_skill(item, level_field="proficiency") for item in _skill_items(data))
        if skill.is_named
    )
    years = data.get("experience_years")
    return ResumeProfile(
        experience_years=float(years) if isinstance(years, (int, float)) else None,
        self_level=_optional_str(data.get("self_level")),
        skills=skills,
    )


def _skill_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Достаёт список навыков из ответа модели, игнорируя мусор."""
    items = data.get("skills")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _parse_skill(item: dict[str, Any], *, level_field: str) -> ExtractedSkill:
    """Разбирает один навык: значения вне диапазона обрезаются."""
    name = item.get("name")
    group = _optional_str(item.get("group"))
    logic = _normalize_logic(item.get("logic"))
    # AND/OR без group не может быть группой: не выдаём ложную логику.
    if group is None:
        logic = "SINGLE"
    return ExtractedSkill(
        name=name.strip() if isinstance(name, str) else "",
        level=_clamp_int(item.get(level_field)),
        weight=_clamp_float(item.get("weight"), default=1.0),
        evidence=_optional_str(item.get("evidence")),
        confidence=_clamp_float(item.get("confidence"), default=0.5),
        group=group[:50] if group is not None else None,
        logic=logic,
    )


def _normalize_logic(value: Any) -> str:
    """Приводит логику требования к SINGLE / AND / OR."""
    if not isinstance(value, str):
        return "SINGLE"
    logic = value.strip().upper()
    return logic if logic in {"SINGLE", "AND", "OR"} else "SINGLE"


def _clamp_int(value: Any, minimum: int = 0, maximum: int = 100) -> int:
    """Округляет и обрезает целое значение в диапазон."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return minimum
    return max(minimum, min(maximum, round(value)))


def _clamp_float(
    value: Any, minimum: float = 0.0, maximum: float = 1.0, default: float = 0.5
) -> float:
    """Обрезает число в диапазон; не-числа дают значение по умолчанию."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return default
    return max(minimum, min(maximum, float(value)))


def _optional_str(value: Any) -> str | None:
    """Строка без пустых хвостов; пустые значения — None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
