"""Тесты состава онтологии (без БД)."""

from collections import Counter

from app.ontology import ONTOLOGY_TOPICS, ONTOLOGY_VERSION, detect_cycles, topic_by_key
from app.services.normalization import normalize_name


def test_ontology_has_enough_topics() -> None:
    """Онтология v2 содержит атомарные темы, а не только broad-ядро."""
    assert len(ONTOLOGY_TOPICS) >= 5


def test_topic_keys_are_unique() -> None:
    """Ключи тем уникальны — по ним идёт синхронизация сида."""
    keys = [topic.key for topic in ONTOLOGY_TOPICS]
    assert len(keys) == len(set(keys))


def test_topics_are_filled() -> None:
    """У каждой темы заполнены название, описание, категория и алиасы."""
    for topic in ONTOLOGY_TOPICS:
        assert topic.name.strip(), f"тема {topic.key} без названия"
        assert len(topic.description.strip()) > 20, f"тема {topic.key} без описания"
        assert topic.category.strip(), f"тема {topic.key} без категории"
        assert topic.aliases, f"тема {topic.key} без алиасов"


def test_prerequisites_reference_existing_topics() -> None:
    """Пререквизиты ссылаются только на существующие темы."""
    keys = {topic.key for topic in ONTOLOGY_TOPICS}
    for topic in ONTOLOGY_TOPICS:
        for prerequisite in topic.prerequisites:
            assert prerequisite in keys, f"тема {topic.key} ссылается на неизвестную {prerequisite}"


def test_no_self_prerequisites() -> None:
    """Тема не является своим же пререквизитом."""
    for topic in ONTOLOGY_TOPICS:
        assert topic.key not in topic.prerequisites


def test_ontology_graph_has_no_cycles() -> None:
    """Граф зависимостей онтологии ацикличен."""
    edges = {topic.key: topic.prerequisites for topic in ONTOLOGY_TOPICS}
    assert detect_cycles(edges) == []


def test_ontology_has_prerequisites() -> None:
    """В онтологии есть хотя бы одна связь — иначе планировщику нечего упорядочивать."""
    edges = {topic.key: topic.prerequisites for topic in ONTOLOGY_TOPICS}
    assert any(edges.values())


def test_topic_by_key() -> None:
    """Поиск темы по ключу работает и для неизвестного ключа даёт None."""
    assert topic_by_key("python") is not None
    assert topic_by_key("python").name == "Python"
    assert topic_by_key("несуществующая-тема") is None


def test_ontology_version_is_positive() -> None:
    """Версия онтологии задана и положительна."""
    assert ONTOLOGY_VERSION >= 2


def test_ontology_covers_atomic_skills() -> None:
    """Онтология v2 состоит из атомарных навыков, а не только из broad-тем."""
    assert len(ONTOLOGY_TOPICS) >= 70
    categories = {topic.category for topic in ONTOLOGY_TOPICS}
    assert {"language", "database", "devops", "cloud", "ml", "web"} <= categories


def test_aliases_are_unique_after_normalization() -> None:
    """Один алиас не может молча указывать на две разные темы."""
    owners: dict[str, str] = {}
    collisions: list[tuple[str, str, str]] = []
    for topic in ONTOLOGY_TOPICS:
        for alias in topic.alias_texts():
            normalized = normalize_name(alias)
            previous = owners.get(normalized)
            if previous is not None and previous != topic.key:
                collisions.append((normalized, previous, topic.key))
            owners[normalized] = topic.key
    assert collisions == [], f"коллизии алиасов: {collisions}"


def test_categories_are_reviewable() -> None:
    """Категории покрывают основные домены и не пустуют."""
    categories = Counter(topic.category for topic in ONTOLOGY_TOPICS)
    assert len(categories) >= 10
    assert all(count >= 1 for count in categories.values())
