# Frontend

React SPA AgentHR. Реализованы вход, загрузка вакансии и резюме с анализом, профиль
знаний: Vite + React 19 + TypeScript, Tailwind CSS 4, shadcn/ui (Base UI), роутинг
(react-router 8), TanStack Query, типизированный API-клиент (типы из OpenAPI).

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
  `VacancyUploadPage` (`/vacancies/new`), `ProfilePage` (`/profile`), `NotFoundPage` (404)
- `src/api/` — `client.ts` (единый клиент: auth, вакансии, резюме, профиль, разрывы,
  `/analysis`, `ApiError`), `schema.d.ts` (типы из OpenAPI, генерируется)
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
- Новая подготовка: `/vacancies/new` → `POST /vacancies` → `POST /resumes` → `POST /analysis`;
  на экране показываются требования, готовность и разрывы, профиль инвалидируется.
- Профиль: `/profile` → `GET /profile` + `GET /vacancies`; для выбранной вакансии —
  `GET /profile/gaps`; параметр `?vacancy=<id>` предвыбирает вакансию.
- Явные состояния loading / error / empty / ready на всех доменных экранах.

## Соглашения

- UI — только shadcn/ui (Base UI); новые компоненты: `npx shadcn@latest add <name>`
- Никаких state-менеджеров: TanStack Query + `useState`
- Версии зависимостей фиксированные (`.npmrc` → `save-exact=true`)
- Tailwind 4 подключён через `@tailwindcss/vite`; тема — в `src/index.css`
- Никаких анимаций и кастомных визуализаций без явного запроса

Экраны продукта (по `AGENTS.md` §7): реализованы `/`, `/login`, `/vacancies/new`, `/profile`;
`/plans/:id`, `/interview/:id`, `/reports/:id` — по плану M3–M5.
