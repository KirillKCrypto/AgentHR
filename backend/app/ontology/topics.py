"""Онтология v1: стартовое ядро графа знаний.

Онтология — словарь верхнего уровня для планирования и gap-анализа,
а не фильтр: навыки вне словаря сохраняются как есть и попадают
в кандидаты на новые темы (см. `app.models.TopicCandidate`).
"""

from dataclasses import dataclass, field

# Версия онтологии: повышается при изменении состава тем
ONTOLOGY_VERSION = 1


@dataclass(frozen=True)
class OntologyTopic:
    """Описание темы онтологии."""

    key: str
    name: str
    description: str
    category: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    prerequisites: tuple[str, ...] = field(default_factory=tuple)

    def alias_texts(self) -> tuple[str, ...]:
        """Названия, по которым навык сопоставляется с темой (включая ключ)."""
        return (self.key, self.name, *self.aliases)


ONTOLOGY_TOPICS: tuple[OntologyTopic, ...] = (
    OntologyTopic(
        key="python",
        name="Python",
        description=(
            "Язык Python: синтаксис, типы данных, итераторы, генераторы, "
            "асинхронность (asyncio), менеджеры пакетов, работа с файлами "
            "и сетевыми запросами, декораторы, тестирование на pytest."
        ),
        category="language",
        aliases=("python3", "питон", "py", "python 3"),
    ),
    OntologyTopic(
        key="oop",
        name="ООП и паттерны проектирования",
        description=(
            "Объектно-ориентированное программирование: классы, наследование, "
            "композиция, интерфейсы, SOLID, принципы GRASP, паттерны проектирования "
            "(singletone, factory, observer, repository, dependency injection)."
        ),
        category="design",
        aliases=(
            "ООП",
            "объектно-ориентированное программирование",
            "design patterns",
            "паттерны проектирования",
            "solid",
        ),
        prerequisites=("python",),
    ),
    OntologyTopic(
        key="algorithms",
        name="Алгоритмы и структуры данных",
        description=(
            "Алгоритмы и структуры данных: массивы, списки, словари, стеки, очереди, "
            "деревья, графы, сортировка, бинарный поиск, хеш-таблицы, оценка "
            "сложности (big O), жадные алгоритмы, динамическое программирование."
        ),
        category="algorithms",
        aliases=(
            "алгоритмы",
            "структуры данных",
            "dsa",
            "data structures and algorithms",
            "сложность алгоритмов",
            "big o",
        ),
    ),
    OntologyTopic(
        key="sql",
        name="SQL",
        description=(
            "Язык SQL: SELECT, JOIN, GROUP BY, HAVING, подзапросы, оконные функции, "
            "индексы, планы запросов, нормализация, представления, диалект PostgreSQL."
        ),
        category="data",
        aliases=(
            "sql",
            "язык запросов",
            "select",
            "postgresql синтаксис",
            "t-sql",
            "базовые запросы",
        ),
    ),
    OntologyTopic(
        key="databases",
        name="Базы данных: проектирование и транзакции",
        description=(
            "Базы данных: проектирование схемы, нормализация и денормализация, "
            "транзакции и уровни изоляции, ACID, MVCC, блокировки, репликация, "
            "партиционирование, миграции схемы, работа с PostgreSQL."
        ),
        category="data",
        aliases=(
            "БД",
            "база данных",
            "database design",
            "проектирование баз данных",
            "acid",
            "mvcc",
            "транзакции",
            "репликация",
        ),
        prerequisites=("sql",),
    ),
    OntologyTopic(
        key="http_api",
        name="Сети, HTTP и REST API",
        description=(
            "Сетевое взаимодействие и веб-протоколы: TCP/IP, HTTP-методы, заголовки, "
            "коды состояний, REST API, версионирование API, аутентификация и авторизация "
            "(OAuth, JWT), идемпотентность, кэширование, клиенты и веб-серверы."
        ),
        category="networking",
        aliases=(
            "http",
            "rest",
            "rest api",
            "http-клиент",
            "web api",
            "api",
            "tcp/ip",
            "сетевое программирование",
        ),
    ),
    OntologyTopic(
        key="testing",
        name="Тестирование и качество кода",
        description=(
            "Тестирование: юнит-, интеграционные и e2e-тесты, pytest, фикстуры, "
            "моки, TDD, покрытие кода, тест-дизайн, рефакторинг, code review, "
            "линтеры и статический анализ."
        ),
        category="quality",
        aliases=(
            "тестирование",
            "unit testing",
            "unit-тесты",
            "pytest",
            "tdd",
            "покрытие кода",
            "тест-дизайн",
            "code review",
        ),
        prerequisites=("python",),
    ),
    OntologyTopic(
        key="git",
        name="Git и организация работы",
        description=(
            "Система контроля версий и процессы разработки: git, ветки и merge, "
            "разрешение конфликтов, rebase, GitHub/GitLab, pull request, "
            "CI/CD, ревью кода, командные процессы разработки."
        ),
        category="process",
        aliases=(
            "git",
            "github",
            "gitlab",
            "система контроля версий",
            "version control",
            "ci/cd",
            "code review",
            "работа в команде",
        ),
    ),
)


def topic_by_key(key: str) -> OntologyTopic | None:
    """Возвращает тему онтологии по ключу."""
    for topic in ONTOLOGY_TOPICS:
        if topic.key == key:
            return topic
    return None
