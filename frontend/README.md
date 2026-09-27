# Frontend

React SPA AgentHR. Реализован каркас с рабочим входом: Vite + React 19 + TypeScript,
Tailwind CSS 4, shadcn/ui (Base UI), роутинг (react-router 8), TanStack Query,
типизированный API-клиент (типы из OpenAPI).

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
- `src/pages/` — экраны: `DashboardPage` (`/`), `LoginPage` (`/login`), `NotFoundPage` (404)
- `src/api/` — `client.ts` (единый клиент: `login`, `register`, `fetchMe`, `ApiError`),
  `schema.d.ts` (типы из OpenAPI, генерируется)
- `src/lib/` — `tokens.ts` (сохранение/очистка токенов в localStorage), `utils.ts` (`cn`)
- `src/components/ui/` — компоненты shadcn/ui (Button, Card, Input, Label)

## Работа с API

- Базовый URL — `VITE_API_BASE_URL` (см. `.env.example`), по умолчанию `http://127.0.0.1:8000`.
- Все запросы — только через `src/api/client.ts`; новые эндпоинты добавлять туда.
- После изменения backend API обновить типы: `npm run generate:api`.
- Поток входа: `/login` → `POST /auth/register` (при регистрации) → `POST /auth/login` →
  токены в localStorage → редирект на `/`; дашборд запрашивает `GET /me`.

## Соглашения

- UI — только shadcn/ui (Base UI); новые компоненты: `npx shadcn@latest add <name>`
- Никаких state-менеджеров: TanStack Query + `useState`
- Версии зависимостей фиксированные (`.npmrc` → `save-exact=true`)
- Tailwind 4 подключён через `@tailwindcss/vite`; тема — в `src/index.css`
- Никаких анимаций и кастомных визуализаций без явного запроса

Экраны продукта (по `AGENTS.md` §7): `/`, `/login`, `/vacancies/new`, `/profile`, `/plans/:id`,
`/interview/:id`, `/reports/:id` — наполняются по плану недель 2–7.
