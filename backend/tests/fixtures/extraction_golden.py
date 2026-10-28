"""Golden-набор для извлечения навыков.

Каждый кейс содержит:
- `text` — исходный текст (вакансия или резюме);
- `llm_response` — записанный ответ модели (используется в тестах как ответ мок-LLM);
- `expected_skills` — эталонные названия навыков;
- `expected_topics` — ожидаемая тема онтологии для каждого навыка (`None` — вне онтологии).

На `llm_response` проверяется весь пайплайн: разбор ответа → нормализация →
сопоставление с онтологией. Скрипт `scripts/eval_extraction.py` прогоняет те же
кейсы на живом LLM и меряет качество извлечения.
"""

from dataclasses import dataclass, field
from typing import Any

JUNIOR_PYTHON_VACANCY = """Вакансия: Python-разработчик (Junior).

Обязанности:
- Разработка REST API на FastAPI;
- Работа с базой PostgreSQL, написание запросов на SQL;
- Написание unit-тестов на pytest;
- Работа с Docker и Git в командном репозитории.

Требования: знание Python, основы SQL, опыт с Docker приветствуется.
"""

SENIOR_BACKEND_VACANCY = """Вакансия: Senior Backend-разработчик.

Ожидания:
- Java и Kafka в продакшене, проектирование микросервисов;
- SQL и оптимизация запросов;
- Kubernetes, Docker, CI/CD;
- Опыт code review и работы в команде.
"""

DATA_ANALYST_VACANCY = """Вакансия: Аналитик данных.

Задачи:
- Написание сложных SQL-запросов к PostgreSQL;
- Подготовка отчётности в Tableau;
- A/B-тесты гипотез;
- Автоматизация расчётов на Python.
"""

BACKEND_RESUME = """Резюме: Backend-разработчик, 2 года опыта.

Разрабатываю сервисы на Python (FastAPI), работаю с PostgreSQL, пишу тесты на pytest.
Собираю и деплою через Docker, код в Git, ревью Pull Request'ов.
"""

JUNIOR_RESUME = """Резюме: Выпускник, ищу позицию junior-разработчика.

В университете изучал SQL, писал простые запросы к PostgreSQL, работал с Git.
Excel, базовое понимание HTML.
"""


@dataclass(frozen=True)
class ExtractionCase:
    """Кейс golden-набора."""

    name: str
    kind: str  # vacancy | resume
    text: str
    llm_response: dict[str, Any]
    expected_skills: tuple[str, ...]
    expected_topics: dict[str, str | None] = field(default_factory=dict)


VACANCY_CASES: tuple[ExtractionCase, ...] = (
    ExtractionCase(
        name="junior_python",
        kind="vacancy",
        text=JUNIOR_PYTHON_VACANCY,
        llm_response={
            "title": "Python-разработчик (Junior)",
            "company": None,
            "level": "junior",
            "skills": [
                {
                    "name": "Python",
                    "required_level": 60,
                    "weight": 1.0,
                    "evidence": "знание Python",
                    "confidence": 0.95,
                },
                {
                    "name": "FastAPI",
                    "required_level": 50,
                    "weight": 0.7,
                    "evidence": "Разработка REST API на FastAPI",
                    "confidence": 0.9,
                },
                {
                    "name": "PostgreSQL",
                    "required_level": 50,
                    "weight": 0.8,
                    "evidence": "Работа с базой PostgreSQL",
                    "confidence": 0.9,
                },
                {
                    "name": "SQL",
                    "required_level": 50,
                    "weight": 0.8,
                    "evidence": "написание запросов на SQL",
                    "confidence": 0.9,
                },
                {
                    "name": "pytest",
                    "required_level": 40,
                    "weight": 0.5,
                    "evidence": "Написание unit-тестов на pytest",
                    "confidence": 0.85,
                },
                {
                    "name": "Docker",
                    "required_level": 30,
                    "weight": 0.4,
                    "evidence": "Работа с Docker",
                    "confidence": 0.8,
                },
                {
                    "name": "Git",
                    "required_level": 30,
                    "weight": 0.3,
                    "evidence": "Работа с Docker и Git в командном репозитории",
                    "confidence": 0.8,
                },
                {
                    "name": "REST API",
                    "required_level": 50,
                    "weight": 0.6,
                    "evidence": "Разработка REST API на FastAPI",
                    "confidence": 0.85,
                },
            ],
        },
        expected_skills=(
            "Python",
            "FastAPI",
            "PostgreSQL",
            "SQL",
            "pytest",
            "Docker",
            "Git",
            "REST API",
        ),
        expected_topics={
            "Python": "python",
            "FastAPI": "fastapi",
            "PostgreSQL": "postgresql",
            "SQL": "sql",
            "pytest": "testing",
            "Docker": "docker",
            "Git": "git",
            "REST API": "http_api",
        },
    ),
    ExtractionCase(
        name="senior_backend",
        kind="vacancy",
        text=SENIOR_BACKEND_VACANCY,
        llm_response={
            "title": "Senior Backend-разработчик",
            "company": None,
            "level": "senior",
            "skills": [
                {
                    "name": "Java",
                    "required_level": 85,
                    "weight": 1.0,
                    "evidence": "Java и Kafka в продакшене",
                    "confidence": 0.9,
                },
                {
                    "name": "Kafka",
                    "required_level": 80,
                    "weight": 0.9,
                    "evidence": "Java и Kafka в продакшене",
                    "confidence": 0.9,
                },
                {
                    "name": "SQL",
                    "required_level": 75,
                    "weight": 0.8,
                    "evidence": "SQL и оптимизация запросов",
                    "confidence": 0.9,
                },
                {
                    "name": "Kubernetes",
                    "required_level": 70,
                    "weight": 0.7,
                    "evidence": "Kubernetes, Docker, CI/CD",
                    "confidence": 0.85,
                },
                {
                    "name": "Docker",
                    "required_level": 60,
                    "weight": 0.6,
                    "evidence": "Kubernetes, Docker, CI/CD",
                    "confidence": 0.85,
                },
                {
                    "name": "CI/CD",
                    "required_level": 60,
                    "weight": 0.5,
                    "evidence": "Kubernetes, Docker, CI/CD",
                    "confidence": 0.8,
                },
                {
                    "name": "code review",
                    "required_level": 50,
                    "weight": 0.4,
                    "evidence": "Опыт code review",
                    "confidence": 0.75,
                },
            ],
        },
        expected_skills=(
            "Java",
            "Kafka",
            "SQL",
            "Kubernetes",
            "Docker",
            "CI/CD",
            "code review",
        ),
        expected_topics={
            "Java": "java",
            "Kafka": "kafka",
            "SQL": "sql",
            "Kubernetes": "kubernetes",
            "Docker": "docker",
            "CI/CD": "cicd",
            "code review": "code_review",
        },
    ),
    ExtractionCase(
        name="data_analyst",
        kind="vacancy",
        text=DATA_ANALYST_VACANCY,
        llm_response={
            "title": "Аналитик данных",
            "company": None,
            "level": "middle",
            "skills": [
                {
                    "name": "SQL",
                    "required_level": 80,
                    "weight": 1.0,
                    "evidence": "Написание сложных SQL-запросов",
                    "confidence": 0.95,
                },
                {
                    "name": "PostgreSQL",
                    "required_level": 60,
                    "weight": 0.7,
                    "evidence": "SQL-запросов к PostgreSQL",
                    "confidence": 0.9,
                },
                {
                    "name": "Tableau",
                    "required_level": 55,
                    "weight": 0.6,
                    "evidence": "Подготовка отчётности в Tableau",
                    "confidence": 0.9,
                },
                {
                    "name": "A/B-тесты",
                    "required_level": 50,
                    "weight": 0.5,
                    "evidence": "A/B-тесты гипотез",
                    "confidence": 0.8,
                },
                {
                    "name": "Python",
                    "required_level": 45,
                    "weight": 0.5,
                    "evidence": "Автоматизация расчётов на Python",
                    "confidence": 0.85,
                },
            ],
        },
        expected_skills=("SQL", "PostgreSQL", "Tableau", "A/B-тесты", "Python"),
        expected_topics={
            "SQL": "sql",
            "PostgreSQL": "postgresql",
            "Tableau": "tableau",
            "A/B-тесты": "ab_testing",
            "Python": "python",
        },
    ),
)


RESUME_CASES: tuple[ExtractionCase, ...] = (
    ExtractionCase(
        name="backend_resume",
        kind="resume",
        text=BACKEND_RESUME,
        llm_response={
            "experience_years": 2,
            "self_level": "middle",
            "skills": [
                {
                    "name": "Python",
                    "proficiency": 70,
                    "evidence": "Разрабатываю сервисы на Python (FastAPI)",
                    "confidence": 0.9,
                },
                {
                    "name": "FastAPI",
                    "proficiency": 60,
                    "evidence": "сервисы на Python (FastAPI)",
                    "confidence": 0.9,
                },
                {
                    "name": "PostgreSQL",
                    "proficiency": 55,
                    "evidence": "работаю с PostgreSQL",
                    "confidence": 0.85,
                },
                {
                    "name": "pytest",
                    "proficiency": 50,
                    "evidence": "пишу тесты на pytest",
                    "confidence": 0.85,
                },
                {
                    "name": "Docker",
                    "proficiency": 45,
                    "evidence": "Собираю и деплою через Docker",
                    "confidence": 0.85,
                },
                {
                    "name": "Git",
                    "proficiency": 50,
                    "evidence": "код в Git, ревью Pull Request'ов",
                    "confidence": 0.8,
                },
            ],
        },
        expected_skills=("Python", "FastAPI", "PostgreSQL", "pytest", "Docker", "Git"),
        expected_topics={
            "Python": "python",
            "FastAPI": "fastapi",
            "PostgreSQL": "postgresql",
            "pytest": "testing",
            "Docker": "docker",
            "Git": "git",
        },
    ),
    ExtractionCase(
        name="junior_resume",
        kind="resume",
        text=JUNIOR_RESUME,
        llm_response={
            "experience_years": 0,
            "self_level": "junior",
            "skills": [
                {
                    "name": "SQL",
                    "proficiency": 35,
                    "evidence": "В университете изучал SQL, писал простые запросы",
                    "confidence": 0.8,
                },
                {
                    "name": "PostgreSQL",
                    "proficiency": 30,
                    "evidence": "простые запросы к PostgreSQL",
                    "confidence": 0.8,
                },
                {
                    "name": "Git",
                    "proficiency": 35,
                    "evidence": "работал с Git",
                    "confidence": 0.8,
                },
                {
                    "name": "Excel",
                    "proficiency": 40,
                    "evidence": "Excel",
                    "confidence": 0.7,
                },
            ],
        },
        expected_skills=("SQL", "PostgreSQL", "Git", "Excel"),
        expected_topics={
            "SQL": "sql",
            "PostgreSQL": "postgresql",
            "Git": "git",
            "Excel": "excel",
        },
    ),
)


ALL_CASES: tuple[ExtractionCase, ...] = VACANCY_CASES + RESUME_CASES
