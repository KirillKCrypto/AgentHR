import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'

import { ApiError, fetchMe } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
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
    content = (
      <div className="flex flex-col gap-4">
        <p className="text-muted-foreground">
          Дашборд подготовки появится здесь: вакансии, активный план и последние интервью.
        </p>
        <div>
          <Button variant="outline" onClick={handleLogout}>
            Выйти
          </Button>
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
