# Frontend

React SPA AgentHR. Реализован каркас: Vite + React 19 + TypeScript, Tailwind CSS 4,
shadcn/ui (Base UI), роутинг (react-router 8), TanStack Query; страницы-заглушки.

## Запуск

```powershell
npm install
npm run dev      # http://localhost:5173
```

## Сборка и линтер

```powershell
npm run build    # tsc + vite build (проверка типов и production-сборка)
npm run lint     # oxlint
```

## Структура

- `src/main.tsx` — точка входа: QueryClientProvider + BrowserRouter
- `src/App.tsx` — шапка и маршруты
- `src/pages/` — экраны (пока заглушки): `DashboardPage` (`/`), `LoginPage` (`/login`),
  `NotFoundPage` (404)
- `src/components/ui/` — компоненты shadcn/ui (Button, Card, Input, Label)
- `src/lib/utils.ts` — утилита `cn`

## Соглашения

- UI — только shadcn/ui (Base UI); новые компоненты: `npx shadcn@latest add <name>`
- Никаких state-менеджеров: TanStack Query + `useState`
- Версии зависимостей фиксированные (`.npmrc` → `save-exact=true`)
- Tailwind 4 подключён через `@tailwindcss/vite`; тема — в `src/index.css`

Экраны продукта (по `AGENTS.md` §7): `/`, `/login`, `/vacancies/new`, `/profile`, `/plans/:id`,
`/interview/:id`, `/reports/:id` — наполняются по плану недель 2–7.
