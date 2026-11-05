# Frontend

React SPA AgentHR. Реализованы вход, профиль знаний с загрузкой резюме (текст или
PDF/DOCX), проверка вакансии по профилю: Vite + React 19 + TypeScript, Tailwind CSS 4,
shadcn/ui (Base UI), роутинг (react-router 8), TanStack Query, типизированный API-клиент
(типы из OpenAPI).

## Запуск

```powershell
npm install
npm run dev      # http://localhost:5173 — нужен запущенный backend (порт 8000)
```

## Сборка, линтер и типы API

```powershell
npm run build        # tsc + vite build (проверка типов и production-сборка)
npm run lint         # oxlint
npm run generate:api # обновить src/api/schema.d.ts из OpenAPI (нужен запущенный backend)
```

## Структура

- `src/main.tsx` — точка входа: QueryClientProvider + BrowserRouter
- `src/App.tsx` — шапка и маршруты
- `src/pages/` — экраны: `DashboardPage` (`/`), `LoginPage` (`/login`),
  `ProfilePage` (`/profile`), `VacancyUploadPage` (`/vacancies/new`),
  `VacancyPage` (`/vacancies/:id`), `PlanPage` (`/plans/:id`), `NotFoundPage` (404)
- `src/components/` — `ResumeUploadCard`, `VacancyAssessment`, `CreatePlanButton`,
  `Gaps`, `PlanSkillTestsCard` + `TopicTest` (10 вопросов по темам плана), `ui/`
- `src/api/` — `client.ts` (auth, вакансии, резюме, профиль, разрывы, планы, вопросы,
  assessments, `/analysis`, `ApiError`), `schema.d.ts` (типы из OpenAPI, генерируется)
- `src/lib/` — `tokens.ts` (токены в localStorage), `useAuthToken.ts` (токен + сброс сессии
  при 401), `errors.ts` (понятные сообщения), `labels.ts` (источники, методы, даты),
  `utils.ts` (`cn`)
- `src/components/ui/` — компоненты shadcn/ui (Button, Card, Input, Label, Textarea, Badge,
  Progress, Table)

## Работа с API

- Базовый URL — `VITE_API_BASE_URL` (см. `.env.example`), по умолчанию `http://127.0.0.1:8000`.
- Все запросы — только через `src/api/client.ts`; новые эндпоинты добавлять туда.
- После изменения backend API обновить типы: `npm run generate:api`.
- Поток входа: `/login` → `POST /auth/register` (при регистрации) → `POST /auth/login` →
  токены в localStorage → редирект на `/`; дашборд запрашивает `GET /me`.
- Профиль: `/profile` → `POST /resumes` (текст) или `POST /resumes/upload` (PDF/DOCX) →
  `GET /profile`. Загруженное резюме дополняет профиль, старые оценки не снижаются.
- Проверка вакансии: `/vacancies/new` → `POST /vacancies` → `GET /profile/gaps`; резюме
  в этой форме не требуется. Если профиль пуст, экран предлагает загрузить резюме.
- Вакансия: `/vacancies/:id` → `GET /vacancies/{id}` + `GET /profile/gaps`; полный текст,
  оценка и рекомендации.
- План: кнопка «Построить план» → `POST /plans` → `/plans/:id` → `GET /plans/{id}`.
  В плане 5–12 тем резюме, цель и число вопросов в банке.
- Вопросы: `GET /questions?topic_key=...&difficulty=...` (пока используется счётчик в плане).
- Профиль и сохранённые вакансии: `/profile` → `GET /profile` + `GET /vacancies`; для
  выбранной вакансии — `GET /profile/gaps`; параметр `?vacancy=<id>` предвыбирает вакансию.
- Проверка навыков: `/profile` → `GET /assessments/topics` → `POST /assessments/{topic}/start`
  → ответы → `POST /assessments/{attempt}/finish`; обновляет `verified_level` в профиле.
- Явные состояния loading / error / empty / ready на всех доменных экранах.

## Соглашения

- UI — только shadcn/ui (Base UI); новые компоненты: `npx shadcn@latest add <name>`
- Никаких state-менеджеров: TanStack Query + `useState`
- Версии зависимостей фиксированные (`.npmrc` → `save-exact=true`)
- Tailwind 4 подключён через `@tailwindcss/vite`; тема — в `src/index.css`
- Никаких анимаций и кастомных визуализаций без явного запроса

Экраны продукта (по [`docs/ROADMAP.md`](../docs/ROADMAP.md) §5): реализованы `/`, `/login`, `/vacancies/new`, `/profile`;
`/plans/:id`, `/interview/:id`, `/reports/:id` — по плану M3–M5.
