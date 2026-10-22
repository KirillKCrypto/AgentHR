"""Онтология AgentHR: стартовое ядро графа знаний и операции с ним.

Сид (`app.ontology.seed`) импортируется напрямую, чтобы запуск
`python -m app.ontology.seed` не выполнял модуль дважды.
"""

from app.ontology.graph import (
    build_edges,
    detect_cycles,
    prerequisites_of,
    topological_order,
    transitive_prerequisites,
)
from app.ontology.topics import ONTOLOGY_TOPICS, ONTOLOGY_VERSION, OntologyTopic, topic_by_key

__all__ = [
    "ONTOLOGY_TOPICS",
    "ONTOLOGY_VERSION",
    "OntologyTopic",
    "build_edges",
    "detect_cycles",
    "prerequisites_of",
    "topic_by_key",
    "topological_order",
    "transitive_prerequisites",
]
