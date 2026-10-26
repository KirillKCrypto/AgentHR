import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'

import { ApiError, fetchMe, listVacancies } from '@/api/client'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { formatDate } from '@/lib/labels'
import { clearTokens, getAccessToken } from '@/lib/tokens'

export default function DashboardPage() {
  const navigate = useNavigate()
  const [token, setToken] = useState<string | null>(() => getAccessToken())

  const { data, isPending, error } = useQuery({
    queryKey: ['me', token],
    queryFn: () => fetchMe(token as string),
    enabled: token !== null,
    retry: false,
  })

  const vacanciesQuery = useQuery({
    queryKey: ['vacancies', token],
    queryFn: () => listVacancies(token as string),
    enabled: token !== null,
    retry: false,
  })

  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      clearTokens()
      setToken(null)
    }
  }, [error])

  function handleLogout() {
    clearTokens()
    setToken(null)
  }

  let description = 'Загружаем профиль…'
  let content: ReactNode = null

  if (token === null) {
    description = 'Вы не вошли в аккаунт.'
    content = <Button onClick={() => navigate('/login')}>Войти</Button>
  } else if (isPending) {
    description = 'Загружаем профиль…'
  } else if (error) {
    description =
      error instanceof ApiError && error.status === 401
        ? 'Сессия истекла — войдите заново.'
        : 'Не удалось загрузить профиль.'
    content = <Button onClick={() => navigate('/login')}>Ко входу</Button>
  } else if (data) {
    description = `Вы вошли как ${data.email}.`
    const vacancies = vacanciesQuery.data ?? []
    content = (
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap gap-2">
          <Link to="/vacancies/new" className={buttonVariants()}>
            Новая подготовка
          </Link>
          <Link to="/profile" className={buttonVariants({ variant: 'outline' })}>
            Профиль знаний
          </Link>
          <Button variant="ghost" onClick={handleLogout}>
            Выйти
          </Button>
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">Последние вакансии</p>
          {vacanciesQuery.isPending ? (
            <p className="text-sm text-muted-foreground">Загружаем вакансии…</p>
          ) : vacanciesQuery.error ? (
            <p className="text-sm text-muted-foreground">Не удалось загрузить вакансии.</p>
          ) : vacancies.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Вакансий пока нет — начните с новой подготовки.
            </p>
          ) : (
            <div className="flex flex-col gap-1">
              {vacancies.map((vacancy) => (
                <Button
                  key={vacancy.id}
                  variant="ghost"
                  className="h-auto justify-between gap-3 py-2"
                  onClick={() => navigate(`/profile?vacancy=${vacancy.id}`)}
                >
                  <span className="font-medium">{vacancy.title ?? 'Без названия'}</span>
                  <span className="text-xs text-muted-foreground">
                    {vacancy.company ? `${vacancy.company} · ` : ''}
                    {formatDate(vacancy.created_at)}
                  </span>
                </Button>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Дашборд</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      {content ? <CardContent>{content}</CardContent> : null}
    </Card>
  )
}
