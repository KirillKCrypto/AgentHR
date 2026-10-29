"""Тесты извлечения навыков: разбор ответа модели и валидация."""

import json

import pytest

from app.llm.base import LLMResponse
from app.llm.mock import MockProvider
from app.services.analysis import (
    AnalysisError,
    extract_resume_skills,
    extract_vacancy_requirements,
)


def _provider(payload: dict) -> MockProvider:
    """Мок-LLM с одним заготовленным структурированным ответом."""
    return MockProvider(responses=[LLMResponse(content=json.dumps(payload, ensure_ascii=False))])


async def test_extract_vacancy_requirements() -> None:
    """Требования вакансии разбираются в структуру."""
    provider = _provider(
        {
            "title": "Python-разработчик",
            "company": "Acme",
            "level": "middle",
            "skills": [
                {
                    "name": "Python",
                    "required_level": 70,
                    "weight": 1.0,
                    "evidence": "знание Python",
                    "confidence": 0.9,
                }
            ],
        }
    )
    result = await extract_vacancy_requirements(provider, "Вакансия Python-разработчик")

    assert result.title == "Python-разработчик"
    assert result.company == "Acme"
    assert result.level == "middle"
    assert len(result.skills) == 1
    assert result.skills[0].name == "Python"
    assert result.skills[0].level == 70
    assert result.skills[0].weight == 1.0
    assert result.skills[0].confidence == 0.9


async def test_vacancy_requirement_groups_are_parsed() -> None:
    """OR/AND-группы и их логика сохраняются, мусорные значения сбрасываются."""
    provider = _provider(
        {
            "title": None,
            "company": None,
            "level": None,
            "skills": [
                {
                    "name": "R",
                    "required_level": 60,
                    "weight": 1.0,
                    "evidence": "R or Java",
                    "confidence": 0.8,
                    "group": "g1",
                    "logic": "OR",
                },
                {
                    "name": "Java",
                    "required_level": 60,
                    "weight": 1.0,
                    "evidence": "R or Java",
                    "confidence": 0.8,
                    "group": "g1",
                    "logic": "OR",
                    "criticality": "nice_to_have",
                },
                {
                    "name": "Docker",
                    "required_level": 70,
                    "weight": 0.8,
                    "evidence": "Docker and Kubernetes",
                    "confidence": 0.8,
                    "group": "g2",
                    "logic": "AND",
                },
                {
                    "name": "Kubernetes",
                    "required_level": 70,
                    "weight": 0.8,
                    "evidence": "Docker and Kubernetes",
                    "confidence": 0.8,
                    "group": "g2",
                    "logic": "AND",
                },
                {
                    "name": "SQL",
                    "required_level": 50,
                    "weight": 0.5,
                    "evidence": "SQL",
                    "confidence": 0.8,
                    "logic": "OR",
                },
            ],
        }
    )
    result = await extract_vacancy_requirements(provider, "Вакансия")

    assert [(skill.name, skill.group, skill.logic) for skill in result.skills] == [
        ("R", "g1", "OR"),
        ("Java", "g1", "OR"),
        ("Docker", "g2", "AND"),
        ("Kubernetes", "g2", "AND"),
        ("SQL", None, "SINGLE"),
    ]
    assert [skill.criticality for skill in result.skills] == [
        "must_have",
        "nice_to_have",
        "must_have",
        "must_have",
        "must_have",
    ]


async def test_invalid_criticality_falls_back_to_must_have() -> None:
    """Неизвестная критичность не ломает разбор и считается обязательной."""
    provider = _provider(
        {
            "title": None,
            "company": None,
            "level": None,
            "skills": [
                {
                    "name": "Python",
                    "required_level": 60,
                    "weight": 1.0,
                    "evidence": None,
                    "confidence": 0.8,
                    "criticality": "required_maybe",
                }
            ],
        }
    )
    result = await extract_vacancy_requirements(provider, "Вакансия")
    assert result.skills[0].criticality == "must_have"


async def test_extract_resume_skills() -> None:
    """Навыки и опыт из резюме разбираются в структуру."""
    provider = _provider(
        {
            "experience_years": 2.5,
            "self_level": "middle",
            "skills": [
                {
                    "name": "SQL",
                    "proficiency": 60,
                    "evidence": "писал запросы",
                    "confidence": 0.8,
                }
            ],
        }
    )
    result = await extract_resume_skills(provider, "Резюме: 2,5 года опыта, SQL")

    assert result.experience_years == 2.5
    assert result.self_level == "middle"
    assert result.skills[0].name == "SQL"
    assert result.skills[0].level == 60


async def test_levels_out_of_range_are_clamped() -> None:
    """Значения вне 0..100 обрезаются, а не ломают разбор."""
    provider = _provider(
        {
            "title": None,
            "company": None,
            "level": None,
            "skills": [
                {
                    "name": "Python",
                    "required_level": 150,
                    "weight": 5.0,
                    "evidence": None,
                    "confidence": -1.0,
                }
            ],
        }
    )
    result = await extract_vacancy_requirements(provider, "Текст вакансии")

    assert result.skills[0].level == 100
    assert result.skills[0].weight == 1.0
    assert result.skills[0].confidence == 0.0


async def test_empty_and_malformed_skills_are_dropped() -> None:
    """Навыки без названия и мусор в ответе отбрасываются."""
    provider = _provider(
        {
            "title": "",
            "company": "  ",
            "level": None,
            "skills": [
                {
                    "name": "   ",
                    "required_level": 50,
                    "weight": 1.0,
                    "evidence": None,
                    "confidence": 0.5,
                },
                "не объект",
                {
                    "name": "SQL",
                    "required_level": 40,
                    "weight": 0.5,
                    "evidence": None,
                    "confidence": 0.5,
                },
            ],
        }
    )
    result = await extract_vacancy_requirements(provider, "Текст вакансии")

    assert result.title is None
    assert result.company is None
    assert [skill.name for skill in result.skills] == ["SQL"]


async def test_missing_skills_key_is_tolerated() -> None:
    """Ответ без ключа skills не считается ошибкой."""
    provider = _provider({"title": "Вакансия", "company": None, "level": None})
    result = await extract_vacancy_requirements(provider, "Текст вакансии")
    assert result.skills == ()


async def test_empty_text_is_rejected() -> None:
    """Пустой текст — понятная ошибка, а не вызов модели."""
    provider = MockProvider()
    with pytest.raises(AnalysisError):
        await extract_vacancy_requirements(provider, "   ")
    with pytest.raises(AnalysisError):
        await extract_resume_skills(provider, "")
    assert provider.calls == []
