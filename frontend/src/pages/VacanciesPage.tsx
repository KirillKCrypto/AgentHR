import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link } from 'react-router'

import { ApiError, listVacancies, type VacancySummary } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { errorMessage } from '@/lib/errors'
import { formatDate } from '@/lib/labels'
import { useAuthToken } from '@/lib/useAuthToken'

export default function VacanciesPage() {
  const { token, expire } = useAuthToken()
  const vacanciesQuery = useQuery<VacancySummary[]>({
    queryKey: ['vacancies', token],
    queryFn: () => listVacancies(token as string),
    enabled: token !== null,
    retry: false,
  })

  useEffect(() => {
    if (vacanciesQuery.error instanceof ApiError && vacanciesQuery.error.status === 401) {
      expire()
    }
  }, [vacanciesQuery.error, expire])

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Вакансии</CardTitle>
          <CardDescription>Войдите, чтобы открыть вакансии.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (vacanciesQuery.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Вакансии</CardTitle>
          <CardDescription>Загружаем вакансии…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (vacanciesQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Вакансии</CardTitle>
          <CardDescription>{errorMessage(vacanciesQuery.error)}</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const vacancies = vacanciesQuery.data ?? []
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Вакансии</CardTitle>
          <CardDescription>
            Сравните требования с профилем и постройте план под конкретную вакансию.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/vacancies/new" className={buttonVariants()}>
            Проверить новую вакансию
          </Link>
        </CardContent>
      </Card>

      {vacancies.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Вакансий пока нет</CardTitle>
            <CardDescription>
              Вставьте текст вакансии — система извлечёт требования и покажет разрывы.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {vacancies.map((vacancy) => (
            <Card key={vacancy.id}>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-2">
                  {vacancy.level ? <Badge variant="outline">{vacancy.level}</Badge> : null}
                </div>
                <CardTitle>{vacancy.title ?? 'Вакансия без названия'}</CardTitle>
                <CardDescription>
                  {vacancy.company ? `${vacancy.company} · ` : ''}
                  {formatDate(vacancy.created_at)}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Link
                  to={`/vacancies/${vacancy.id}`}
                  className={buttonVariants({ variant: 'outline' })}
                >
                  Открыть вакансию
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
