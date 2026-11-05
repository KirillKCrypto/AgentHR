import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, Route, Routes, useNavigate } from 'react-router'

import { ApiError, fetchMe } from '@/api/client'
import DashboardPage from '@/pages/DashboardPage'
import LoginPage from '@/pages/LoginPage'
import NotFoundPage from '@/pages/NotFoundPage'
import PlanPage from '@/pages/PlanPage'
import ProfilePage from '@/pages/ProfilePage'
import VacancyPage from '@/pages/VacancyPage'
import VacancyUploadPage from '@/pages/VacancyUploadPage'
import { clearTokens, getAccessToken, subscribeAuth } from '@/lib/tokens'

function App() {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b">
        <nav className="mx-auto flex h-14 max-w-5xl items-center gap-4 px-4 text-sm">
          <Link to="/" className="font-medium">
            AgentHR
          </Link>
          <Link
            to="/profile"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            Профиль знаний
          </Link>
          <Link
            to="/vacancies/new"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            Проверить вакансию
          </Link>
          <div className="ml-auto">
            <UserBadge />
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-10">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/vacancies/new" element={<VacancyUploadPage />} />
          <Route path="/vacancies/:vacancyId" element={<VacancyPage />} />
          <Route path="/plans/:planId" element={<PlanPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  )
}

function UserBadge() {
  const [token, setToken] = useState<string | null>(() => getAccessToken())

  useEffect(() => subscribeAuth(() => setToken(getAccessToken())), [])

  if (token === null) {
    return (
      <Link to="/login" className="text-muted-foreground transition-colors hover:text-foreground">
        Вход
      </Link>
    )
  }

  return <UserLink token={token} />
}

function UserLink({ token }: { token: string }) {
  const navigate = useNavigate()
  const { data, isPending, error } = useQuery({
    queryKey: ['me', token],
    queryFn: () => fetchMe(token),
    retry: false,
  })

  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      clearTokens()
      navigate('/login', { replace: true })
    }
  }, [error, navigate])

  if (isPending) {
    return <span className="text-muted-foreground">Загрузка…</span>
  }
  if (!data) {
    return (
      <Link to="/login" className="text-muted-foreground transition-colors hover:text-foreground">
        Вход
      </Link>
    )
  }

  return (
    <div className="flex items-center gap-3">
      <Link
        to="/profile"
        title={data.email}
        className="max-w-64 truncate font-medium transition-colors hover:text-foreground"
      >
        {data.email}
      </Link>
      <button
        type="button"
        onClick={() => {
          clearTokens()
          navigate('/login', { replace: true })
        }}
        className="text-muted-foreground transition-colors hover:text-foreground"
      >
        Выйти
      </button>
    </div>
  )
}

export default App
