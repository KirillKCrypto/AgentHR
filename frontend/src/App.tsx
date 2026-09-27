import { Link, Route, Routes } from 'react-router'

import DashboardPage from '@/pages/DashboardPage'
import LoginPage from '@/pages/LoginPage'
import NotFoundPage from '@/pages/NotFoundPage'

function App() {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b">
        <nav className="mx-auto flex h-14 max-w-3xl items-center gap-4 px-4 text-sm">
          <Link to="/" className="font-medium">
            AgentHR
          </Link>
          <Link
            to="/login"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            Вход
          </Link>
        </nav>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
