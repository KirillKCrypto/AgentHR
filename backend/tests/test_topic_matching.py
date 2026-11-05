"""Нормализация составных названий и версий в навыках."""

from app.services.analysis import ExtractedSkill
from app.services.normalization import SkillMatcher, strip_version_suffix
from app.services.profile import _expand_composite_skills
from app.services.topics import load_packaged_topic_index
from tests.conftest import ApiUser


def test_strip_version_suffix() -> None:
    """Версия в конце названия отбрасывается, значимые цифры остаются."""
    assert strip_version_suffix("Python 3.11") == "Python"
    assert strip_version_suffix("React 18") == "React"
    assert strip_version_suffix("C# 12") == "C#"
    assert strip_version_suffix("ISO 27001") == "ISO 27001"


async def test_matcher_ignores_version_suffix() -> None:
    """«Python 3.11» сопоставляется с темой Python."""
    matcher = SkillMatcher(load_packaged_topic_index())
    match = await matcher.match("Python 3.11")

    assert match.topic_key == "python"


async def test_matcher_understands_oop_synonym() -> None:
    """Русское полное название ООП ведёт в тему oop."""
    matcher = SkillMatcher(load_packaged_topic_index())
    match = await matcher.match("объектно-ориентированное программирование")

    assert match.topic_key == "oop"


def test_composite_skill_is_split_when_parts_are_known() -> None:
    """«LightGBM/XGBoost» разбивается на два известных навыка."""
    index = load_packaged_topic_index()
    skills = [ExtractedSkill(name="LightGBM/XGBoost", level=55)]

    expanded = _expand_composite_skills(skills, index)

    assert sorted(skill.name for skill in expanded) == ["LightGBM", "XGBoost"]


def test_composite_skill_stays_when_parts_are_unknown() -> None:
    """«CI/CD» не дробится, если части не являются темами."""
    index = load_packaged_topic_index()
    skills = [ExtractedSkill(name="CI/CD", level=70)]

    expanded = _expand_composite_skills(skills, index)

    assert [skill.name for skill in expanded] == ["CI/CD"]


def test_composite_parts_are_deduplicated() -> None:
    """Одинаковые части не создают дубликаты навыков."""
    index = load_packaged_topic_index()
    skills = [
        ExtractedSkill(name="Docker/Kubernetes", level=60),
        ExtractedSkill(name="Docker", level=70),
    ]

    expanded = _expand_composite_skills(skills, index)

    assert sorted(skill.name for skill in expanded) == ["Docker", "Kubernetes"]


async def test_upload_splits_composite_vacancy_skill(api_user: ApiUser) -> None:
    """Вакансия с «LightGBM/XGBoost» получает две строки навыков."""
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "ML-инженер",
        "company": "Acme",
        "level": "middle",
        "skills": [
            {
                "name": "LightGBM/XGBoost",
                "required_level": 60,
                "weight": 1.0,
                "evidence": "градиентный бустинг",
                "confidence": 0.9,
            }
        ],
    }

    response = await api_user.client.post(
        "/vacancies",
        json={"title": "ML-инженер", "raw_text": "Нужен LightGBM/XGBoost"},
        headers=api_user.headers,
    )

    assert response.status_code == 201, response.text
    skills = response.json()["skills"]
    assert sorted(skill["raw_name"] for skill in skills) == ["LightGBM", "XGBoost"]
    assert all(skill["topic"] is not None for skill in skills)
