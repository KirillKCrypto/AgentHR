"""Читаемость текста рекомендаций gap-анализа."""

from app.services.gaps import GapItem, _recommendations


def test_recommendation_reason_is_readable() -> None:
    """Причина рекомендации на русском, без двойной кодировки."""
    item = GapItem(
        skill_name="Python",
        required_level=80,
        user_level=20,
        gap=60,
        satisfied=False,
        weight=0.7,
    )

    recommendation = _recommendations([item])[0]

    assert recommendation.reason.startswith("Обязательное требование, вес 0.70")
    assert "не хватает 60 из 80" in recommendation.reason
    assert "Р" not in recommendation.reason
