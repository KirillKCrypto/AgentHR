"""Тесты операций над графом зависимостей тем (без БД)."""

import pytest

from app.ontology import (
    build_edges,
    detect_cycles,
    prerequisites_of,
    topological_order,
    transitive_prerequisites,
)


def test_build_edges_groups_prerequisites() -> None:
    """Пары (тема, пререквизит) собираются в словарь."""
    edges = build_edges([("oop", "python"), ("databases", "sql"), ("oop", "algorithms")])
    assert edges == {"oop": ["python", "algorithms"], "databases": ["sql"]}


def test_detect_cycles_finds_cycle() -> None:
    """Цикл в графе находится."""
    edges = {"a": ["b"], "b": ["c"], "c": ["a"]}
    cycles = detect_cycles(edges)
    assert cycles
    assert cycles[0][0] == cycles[0][-1]


def test_detect_cycles_accepts_dag() -> None:
    """Ациклический граф не даёт циклов."""
    edges = {"oop": ["python"], "databases": ["sql"]}
    assert detect_cycles(edges) == []


def test_topological_order_places_prerequisites_first() -> None:
    """В топологическом порядке пререквизит идёт раньше зависимой темы."""
    edges = {
        "oop": ["python"],
        "testing": ["python"],
        "databases": ["sql"],
        "advanced": ["oop", "databases"],
    }
    order = topological_order(edges)
    assert order.index("python") < order.index("oop")
    assert order.index("sql") < order.index("databases")
    assert order.index("oop") < order.index("advanced")
    assert order.index("databases") < order.index("advanced")
    assert set(order) == {"python", "oop", "testing", "sql", "databases", "advanced"}


def test_topological_order_raises_on_cycle() -> None:
    """На цикле топологическая сортировка падает с понятной ошибкой."""
    with pytest.raises(ValueError, match="цикл"):
        topological_order({"a": ["b"], "b": ["a"]})


def test_prerequisites_of_returns_direct_only() -> None:
    """Прямые пререквизиты не включают транзитивные."""
    edges = {"advanced": ["oop"], "oop": ["python"]}
    assert prerequisites_of(edges, "advanced") == ["oop"]
    assert prerequisites_of(edges, "python") == []


def test_transitive_prerequisites() -> None:
    """Транзитивные пререквизиты собираются по цепочке."""
    edges = {"advanced": ["oop"], "oop": ["python"], "python": []}
    assert transitive_prerequisites(edges, "advanced") == {"oop", "python"}
    assert transitive_prerequisites(edges, "python") == set()


def test_transitive_prerequisites_ignores_self() -> None:
    """Тема не попадает в множество своих пререквизитов даже при петле."""
    edges = {"a": ["a"]}
    assert transitive_prerequisites(edges, "a") == set()
