"""Работа с графом зависимостей тем (REQUIRES).

Граф хранится в БД как `topic_prerequisites`, но проверки целостности
(циклы, топологический порядок) нужны и на данных онтологии, и на
данных из БД — поэтому логика вынесена отдельно и не зависит от ORM.
"""

from collections.abc import Iterable, Mapping


def build_edges(pairs: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    """Собирает словарь «тема → пререквизиты» из пар (тема, пререквизит)."""
    edges: dict[str, list[str]] = {}
    for topic, prerequisite in pairs:
        edges.setdefault(topic, []).append(prerequisite)
    return edges


def detect_cycles(edges: Mapping[str, Iterable[str]]) -> list[list[str]]:
    """Ищет циклы в графе зависимостей.

    Возвращает список циклов (каждый — путь ключей, где последний элемент
    совпадает с первым). Пустой список означает, что граф ацикличен.
    """
    cycles: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        visiting.add(node)
        stack.append(node)
        for neighbour in edges.get(node, ()):
            if neighbour in visiting:
                start = stack.index(neighbour)
                cycles.append([*stack[start:], neighbour])
                continue
            if neighbour not in visited:
                visit(neighbour)
        stack.pop()
        visiting.discard(node)
        visited.add(node)

    for node in edges:
        if node not in visited:
            visit(node)
    return cycles


def topological_order(edges: Mapping[str, Iterable[str]]) -> list[str]:
    """Возвращает темы в порядке «от пререквизитов к зависимым».

    Темы без пререквизитов идут первыми. Если в графе есть цикл —
    выбрасывается `ValueError`.
    """
    cycles = detect_cycles(edges)
    if cycles:
        raise ValueError(f"В графе зависимостей есть цикл: {cycles[0]}")

    # Учитываем и темы, которые встречаются только как пререквизит
    nodes: set[str] = set()
    for node, prerequisites in edges.items():
        nodes.add(node)
        nodes.update(prerequisites)

    remaining = {node: set(edges.get(node, ())) for node in nodes}
    order: list[str] = []
    while remaining:
        ready = sorted(node for node, prerequisites in remaining.items() if not prerequisites)
        if not ready:
            raise ValueError("Не удалось упорядочить темы: в графе есть цикл")
        for node in ready:
            order.append(node)
            del remaining[node]
        for prerequisites in remaining.values():
            prerequisites.difference_update(ready)
    return order


def prerequisites_of(edges: Mapping[str, Iterable[str]], key: str) -> list[str]:
    """Прямые пререквизиты темы."""
    return list(edges.get(key, ()))


def transitive_prerequisites(edges: Mapping[str, Iterable[str]], key: str) -> set[str]:
    """Все пререквизиты темы (транзитивно), без самой темы."""
    result: set[str] = set()
    stack = list(edges.get(key, ()))
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(edges.get(current, ()))
    result.discard(key)
    return result
