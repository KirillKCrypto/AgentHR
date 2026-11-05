import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router'

import {
  ApiError,
  fetchGaps,
  fetchProfile,
  fetchVacancy,
  type GapAnalysisRead,
  type VacancyRead,
} from '@/api/client'
import { buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { VacancyAssessment } from '@/components/VacancyAssessment'
import { errorMessage } from '@/lib/errors'
import { formatDate } from '@/lib/labels'
import { useAuthToken } from '@/lib/useAuthToken'

export default function VacancyPage() {
  const { vacancyId } = useParams<{ vacancyId: string }>()
  const { token, expire } = useAuthToken()

  const vacancyQuery = useQuery<VacancyRead>({
    queryKey: ['vacancy', vacancyId, token],
    queryFn: () => fetchVacancy(vacancyId as string, token as string),
    enabled: token !== null && Boolean(vacancyId),
    retry: false,
  })

  const gapsQuery = useQuery<GapAnalysisRead>({
    queryKey: ['gaps', vacancyId, token],
    queryFn: () => fetchGaps(vacancyId as string, token as string),
    enabled: token !== null && Boolean(vacancyId),
    retry: false,
  })

  const profileQuery = useQuery({
    queryKey: ['profile', token],
    queryFn: () => fetchProfile(token as string),
    enabled: token !== null,
    retry: false,
  })

  const error = vacancyQuery.error ?? gapsQuery.error ?? profileQuery.error
  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      expire()
    }
  }, [error, expire])

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Вакансия</CardTitle>
          <CardDescription>Войдите, чтобы открыть вакансию.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (vacancyQuery.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Вакансия</CardTitle>
          <CardDescription>Загружаем вакансию…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (vacancyQuery.isError || !vacancyQuery.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Вакансия</CardTitle>
          <CardDescription>{errorMessage(vacancyQuery.error)}</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/profile" className={buttonVariants({ variant: 'outline' })}>
            К профилю
          </Link>
        </CardContent>
      </Card>
    )
  }

  const vacancy = vacancyQuery.data
  const gaps = gapsQuery.data
  const hasProfile = (profileQuery.data?.topics.length ?? 0) > 0

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{vacancy.title ?? 'Вакансия без названия'}</CardTitle>
          <CardDescription>
            {vacancy.company ? `${vacancy.company} · ` : ''}
            {formatDate(vacancy.created_at)}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <p className="mb-2 text-sm font-medium">Текст вакансии</p>
            <div className="max-h-96 overflow-auto rounded-md border bg-muted/40 p-4">
              <pre className="whitespace-pre-wrap font-sans text-sm">{vacancy.raw_text}</pre>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to={`/profile?vacancy=${vacancy.id}`}
              className={buttonVariants({ variant: 'outline' })}
            >
              Профиль и разрывы
            </Link>
            <Link to="/vacancies/new" className={buttonVariants({ variant: 'ghost' })}>
              Проверить другую вакансию
            </Link>
          </div>
        </CardContent>
      </Card>

      {gaps ? (
        <VacancyAssessment vacancy={vacancy} gaps={gaps} hasProfile={hasProfile} />
      ) : gapsQuery.isError ? (
        <Card>
          <CardHeader>
            <CardTitle>Оценка недоступна</CardTitle>
            <CardDescription>{errorMessage(gapsQuery.error)}</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Оценка</CardTitle>
            <CardDescription>Считаем готовность…</CardDescription>
          </CardHeader>
        </Card>
      )}
    </div>
  )
}
