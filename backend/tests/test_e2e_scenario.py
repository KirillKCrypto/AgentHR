"""E2E-скелет сквозного сценария M2 на уровне HTTP API.

Сценарий: вакансия → резюме → профиль знаний → разрывы → совместный анализ →
повторная вакансия с переиспользованием накопленного профиля.
"""

from tests.conftest import RESUME_TEXT, VACANCY_TEXT, ApiUser


async def test_full_preparation_scenario(api_user: ApiUser) -> None:
    """Пользователь проходит сценарий M2 целиком, профиль переиспользуется."""
    # 1. Вакансия: извлечение навыков и нормализация к онтологии
    vacancy_response = await api_user.client.post(
        "/vacancies",
        json={"title": "Python-разработчик", "company": "Acme", "raw_text": VACANCY_TEXT},
        headers=api_user.headers,
    )
    assert vacancy_response.status_code == 201, vacancy_response.text
    vacancy = vacancy_response.json()
    assert {skill["raw_name"] for skill in vacancy["skills"]} == {
        "Python",
        "PostgreSQL",
        "Kafka",
    }

    # 2. Резюме: извлечение навыков и пересборка профиля знаний
    resume_response = await api_user.client.post(
        "/resumes",
        json={"title": "Резюме", "raw_text": RESUME_TEXT},
        headers=api_user.headers,
    )
    assert resume_response.status_code == 201, resume_response.text
    resume = resume_response.json()

    # 3. Профиль: темы онтологии + навыки вне словаря
    profile_response = await api_user.client.get("/profile", headers=api_user.headers)
    assert profile_response.status_code == 200
    profile = profile_response.json()
    topics = {topic["topic_key"]: topic for topic in profile["topics"]}
    assert set(topics) == {"python", "sql"}
    assert topics["python"]["proficiency"] == 75
    assert topics["python"]["source"] == "resume"
    assert [skill["raw_name"] for skill in profile["unmatched_skills"]] == ["Docker"]

    # 4. Разрывы под загруженную вакансию
    gaps_response = await api_user.client.get(
        "/profile/gaps",
        params={"vacancy_id": vacancy["id"]},
        headers=api_user.headers,
    )
    assert gaps_response.status_code == 200, gaps_response.text
    gaps = gaps_response.json()
    gaps_by_skill = {item["skill_name"]: item for item in gaps["items"]}
    assert gaps_by_skill["Python"]["satisfied"] is True
    assert gaps_by_skill["PostgreSQL"]["gap"] == 10
    assert gaps_by_skill["Kafka"]["topic_key"] is None
    assert gaps["unmatched_count"] == 1

    # 5. Совместный анализ по сохранённым документам — без новых вызовов LLM
    analysis_response = await api_user.client.post(
        "/analysis",
        json={"vacancy_id": vacancy["id"], "resume_id": resume["id"]},
        headers=api_user.headers,
    )
    assert analysis_response.status_code == 200, analysis_response.text
    analysis = analysis_response.json()
    assert analysis["gaps"]["overall_readiness"] == gaps["overall_readiness"]
    calls_after_analysis = len(api_user.provider.calls)

    # 6. Новая вакансия использует накопленный профиль
    api_user.provider.responses["vacancy_requirements"] = {
        "title": "Junior Python-разработчик",
        "level": "junior",
        "skills": [
            {
                "name": "Python",
                "required_level": 60,
                "weight": 1.0,
                "evidence": "Базовый Python",
                "confidence": 0.9,
            }
        ],
    }
    second_response = await api_user.client.post(
        "/vacancies",
        json={"title": "Junior Python-разработчик", "raw_text": "Нужен Python."},
        headers=api_user.headers,
    )
    assert second_response.status_code == 201, second_response.text
    second = second_response.json()

    second_gaps_response = await api_user.client.get(
        "/profile/gaps",
        params={"vacancy_id": second["id"]},
        headers=api_user.headers,
    )
    assert second_gaps_response.status_code == 200
    second_gaps = second_gaps_response.json()
    assert second_gaps["overall_readiness"] == 1.0
    assert second_gaps["items"][0]["user_level"] == 75

    # 7. Чтение и анализ не меняют профиль
    profile_after = await api_user.client.get("/profile", headers=api_user.headers)
    assert profile_after.status_code == 200
    assert {
        topic["topic_key"]: topic["proficiency"]
        for topic in profile_after.json()["topics"]
    } == {"python": 75, "sql": 50}
    assert profile_after.json()["unmatched_skills"] == profile["unmatched_skills"]

    # Единственный дополнительный вызов модели — извлечение второй вакансии
    assert len(api_user.provider.calls) == calls_after_analysis + 1
