"""Eval качества извлечения навыков на живой модели.

Прогоняет golden-набор (`tests/fixtures/extraction_golden.py`) через реальный
LLM-провайдер и меряет качество извлечения и сопоставления с онтологией.

Запуск (нужен `LLM_PROVIDER=openai` и ключ):

    uv run python scripts/eval_extraction.py
    uv run python scripts/eval_extraction.py --min-f1 0.8 --show-skills
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.llm.factory import create_llm_provider
from app.services.analysis import (
    extract_resume_skills,
    extract_vacancy_requirements,
)
from app.services.evaluation import precision_recall
from app.services.normalization import SkillMatcher
from app.services.topics import load_packaged_topic_index
from tests.fixtures.extraction_golden import ALL_CASES, ExtractionCase


async def run_case(case: ExtractionCase, provider, matcher: SkillMatcher) -> dict[str, float]:
    """Прогоняет один кейс и возвращает метрики."""
    if case.kind == "vacancy":
        result = await extract_vacancy_requirements(provider, case.text)
    else:
        result = await extract_resume_skills(provider, case.text)

    names = [skill.name for skill in result.skills]
    precision, recall, f1 = precision_recall(case.expected_skills, names)

    matches = await matcher.match_many(names)
    mapping = dict(zip(names, [match.topic_key for match in matches], strict=True))
    expected = {
        name: case.expected_topics.get(name)
        for name in case.expected_skills
        if name in case.expected_topics
    }
    checked = {name: topic for name, topic in expected.items() if name in mapping}
    topic_hits = sum(1 for name, topic in checked.items() if mapping[name] == topic)

    if args.show_skills:
        print(f"    извлечено: {names}")
        print(f"    темы: {mapping}")

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "topic_accuracy": topic_hits / len(checked) if checked else 1.0,
    }


def parse_args() -> argparse.Namespace:
    """Параметры запуска."""
    parser = argparse.ArgumentParser(description="Eval качества извлечения навыков")
    parser.add_argument(
        "--min-f1",
        type=float,
        default=0.0,
        help="Порог F1, ниже которого скрипт завершится с ошибкой (0 — не проверять)",
    )
    parser.add_argument(
        "--show-skills",
        action="store_true",
        help="Показывать извлечённые навыки и сопоставленные темы",
    )
    return parser.parse_args()


args = parse_args()


async def main() -> int:
    """Прогоняет все кейсы и печатает сводку."""
    settings = get_settings()
    if settings.llm_provider == "mock":
        print(
            "LLM_PROVIDER=mock — оценивать нечего: нужен реальный провайдер.\n"
            "Задайте LLM_PROVIDER=openai, OPENAI_API_KEY и OPENAI_MODEL.",
            file=sys.stderr,
        )
        return 2
    provider = create_llm_provider(settings)
    matcher = SkillMatcher(load_packaged_topic_index())

    rows = []
    try:
        for case in ALL_CASES:
            metrics = await run_case(case, provider, matcher)
            rows.append((case, metrics))
            print(
                f"{case.name:20} precision={metrics['precision']:.3f} "
                f"recall={metrics['recall']:.3f} f1={metrics['f1']:.3f} "
                f"темы={metrics['topic_accuracy']:.3f}"
            )
    finally:
        await provider.close()

    if not rows:
        print("Нет кейсов")
        return 1

    count = len(rows)
    mean_f1 = sum(metrics["f1"] for _, metrics in rows) / count
    mean_precision = sum(metrics["precision"] for _, metrics in rows) / count
    mean_recall = sum(metrics["recall"] for _, metrics in rows) / count
    mean_topics = sum(metrics["topic_accuracy"] for _, metrics in rows) / count

    print(
        f"\nИтого по {count} кейсам: precision={mean_precision:.3f} "
        f"recall={mean_recall:.3f} f1={mean_f1:.3f} темы={mean_topics:.3f}"
    )
    if args.min_f1 and mean_f1 < args.min_f1:
        print(f"F1 ниже порога {args.min_f1:.3f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
