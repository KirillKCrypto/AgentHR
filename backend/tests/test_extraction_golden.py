"""Golden-тест пайплайна извлечения: разбор ответа → нормализация → темы.

Ответы модели зафиксированы в golden-наборе, поэтому тест проверяет весь
конвейер детерминированно. Качество извлечения на живой модели меряет
скрипт `scripts/eval_extraction.py` на тех же кейсах.
"""

import json

import pytest

from app.llm.base import LLMResponse
from app.llm.mock import MockProvider
from app.services.analysis import extract_resume_skills, extract_vacancy_requirements
from app.services.evaluation import precision_recall
from app.services.normalization import SkillMatcher
from app.services.topics import load_packaged_topic_index
from tests.fixtures.extraction_golden import ALL_CASES, ExtractionCase


def _provider(case: ExtractionCase) -> MockProvider:
    return MockProvider(
        responses=[LLMResponse(content=json.dumps(case.llm_response, ensure_ascii=False))]
    )


async def _extract(case: ExtractionCase):
    provider = _provider(case)
    if case.kind == "vacancy":
        result = await extract_vacancy_requirements(provider, case.text)
    else:
        result = await extract_resume_skills(provider, case.text)
    return [skill.name for skill in result.skills]


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda case: case.name)
async def test_golden_case_extracts_expected_skills(case: ExtractionCase) -> None:
    """Из ответа модели извлекаются ровно эталонные навыки."""
    names = await _extract(case)
    precision, recall, f1 = precision_recall(case.expected_skills, names)
    assert precision == 1.0, f"{case.name}: лишние навыки {set(names) - set(case.expected_skills)}"
    assert recall == 1.0, f"{case.name}: потеряны навыки {set(case.expected_skills) - set(names)}"
    assert f1 == 1.0


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda case: case.name)
async def test_golden_case_maps_to_expected_topics(case: ExtractionCase) -> None:
    """Навыки сопоставляются с ожидаемыми темами онтологии."""
    names = await _extract(case)
    matcher = SkillMatcher(load_packaged_topic_index())
    matches = await matcher.match_many(names)
    mapping = dict(zip(names, [match.topic_key for match in matches], strict=True))

    assert mapping == case.expected_topics


def test_packaged_ontology_covers_expected_topics() -> None:
    """Все ожидаемые темы golden-набора есть в онтологии v1."""
    index = load_packaged_topic_index()
    keys = {topic.key for topic in index.topics}
    for case in ALL_CASES:
        for topic_key in case.expected_topics.values():
            if topic_key is not None:
                assert topic_key in keys, f"{case.name}: тема {topic_key} отсутствует в онтологии"


def test_golden_set_is_not_empty() -> None:
    """Golden-набор непустой и покрывает оба типа документов."""
    assert len(ALL_CASES) >= 4
    assert {case.kind for case in ALL_CASES} == {"vacancy", "resume"}
