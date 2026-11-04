# ASSESSMENT — мини-тесты навыков

Проверяемые мини-тесты отделяют **заявленный** уровень от **подтверждённого**.

## Зачем

Резюме — самоотчёт. LLM извлекает `proficiency` из текста, но это не измерение.
Мини-тест даёт детерминированный `verified_level` и повышает доверие к профилю.

## Модель данных

- `assessment_questions` — банк вопросов:
  `key`, `topic_id`, `difficulty`, `kind`, `prompt`, `options`, `correct_key`,
  `explanation`, `status`, `version`.
- `assessment_attempts` — попытка:
  `user_id`, `topic_id`, `status`, `question_ids`, `score`, `test_level`,
  `confidence`, `started_at`, `finished_at`.
- `assessment_answers` — ответы:
  `attempt_id`, `question_id`, `answer_key`, `is_correct`, `score`.
- `user_skill_states`:
  `claimed_level`, `verified_level`, `evidence_strength`, `proficiency`.

`proficiency` — эффективный уровень. `claimed_level` — из резюме.
`verified_level` — из теста.

## Банк вопросов

MVP: 8 тем × 20 вопросов = 160.

| Тема | Ключ |
|---|---|
| Python | `python` |
| SQL | `sql` |
| PostgreSQL | `postgresql` |
| Docker | `docker` |
| Git | `git` |
| HTTP/REST | `http_api` |
| ООП | `oop` |
| Алгоритмы | `algorithms` |

Сложности: 20, 40, 60, 75, 90 — по 4 вопроса на каждую.  
Одна попытка берёт 10 вопросов: по 2 на каждую сложность.  
Тип MVP — `single_choice`; позже — code output, SQL-запросы, открытые ответы.

Банк лежит в `backend/app/assessment/questions.py`, сид — в `seed.py`.
Runtime-оценка не использует LLM.

## Скоринг

```text
earned = Σ(difficulty вопроса, если ответ верный)
max = Σ(difficulty всех вопросов)
score = earned / max
test_level = round(20 + 75 × score)
confidence = min(0.95, 0.5 + 0.09 × answered)
```

Пример: 6 из 10 верных, суммарная сложность 570, earned 350 → level 66.

После завершения:

```text
claimed_level = старый proficiency (если ещё не задан)
verified_level = test_level
proficiency = test_level
confidence = confidence теста
source = assessment
evidence_strength = 0.9
```

## API

- `GET /assessments/topics` — доступные темы;
- `POST /assessments/{topic_key}/start` — старт/продолжение;
- `POST /assessments/{attempt_id}/answers` — ответ;
- `POST /assessments/{attempt_id}/finish` — результат и разбор.

## UI

В профиле — карточка **«Проверка навыков»**:
выбор темы → 10 вопросов → результат с разбором ошибок.
После завершения профиль и gap-анализ пересчитываются.

## Ограничения MVP

- фиксированные 10 вопросов, без адаптивного выбора;
- только single choice;
- один тест на тему: повторное прохождение запрещено;
- нет таймера;
- банк вопросов курируется вручную.

## Дальше

- адаптивный выбор вопросов;
- расширение банка до 15–20 на тему;
- SQL/code-output и открытые ответы с рубриками;
- readiness-гейт: `verified_level` для `must_have`.
