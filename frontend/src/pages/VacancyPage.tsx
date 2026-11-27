import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router'

import {
  ApiError,
  fetchGaps,
  fetchProfile,
  fetchVacancy,
  listPlans,
  type GapAnalysisRead,
  type PlanSummary,
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
import { CreatePlanButton } from '@/components/CreatePlanButton'
import { VacancyAssessment } from '@/components/VacancyAssessment'
import { StartInterviewButton } from '@/components/StartInterviewButton'
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
  const plansQuery = useQuery<PlanSummary[]>({
    queryKey: ['plans', token],
    queryFn: () => listPlans(token as string),
    enabled: token !== null,
    retry: false,
  })

  const error =
    vacancyQuery.error ?? gapsQuery.error ?? profileQuery.error ?? plansQuery.error
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
          <Link to="/profile/skills" className={buttonVariants({ variant: 'outline' })}>
            К профилю
          </Link>
        </CardContent>
      </Card>
    )
  }

  const vacancy = vacancyQuery.data
  const gaps = gapsQuery.data
  const hasProfile = (profileQuery.data?.topics.length ?? 0) > 0
  const activePlan = (plansQuery.data ?? []).find(
    (plan) => plan.vacancy_id === vacancy.id && plan.status === 'active',
  )

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
              to={`/profile/skills?vacancy=${vacancy.id}`}
              className={buttonVariants({ variant: 'outline' })}
            >
              Профиль и разрывы
            </Link>
            <StartInterviewButton vacancyId={vacancy.id} />
            <Link to="/vacancies/new" className={buttonVariants({ variant: 'ghost' })}>
              Проверить другую вакансию
            </Link>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>План по вакансии</CardTitle>
          <CardDescription>
            Все обязательные требования попадают в этот план, даже если разрыв уже
            закрыт резюме.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          {activePlan ? (
            <>
              <span className="text-sm text-muted-foreground">
                {activePlan.title} · {activePlan.topic_count} тем
              </span>
              <Link
                to={`/plans/${activePlan.id}`}
                className={buttonVariants({ variant: 'outline' })}
              >
                Открыть план
              </Link>
            </>
          ) : (
            <CreatePlanButton vacancyId={vacancy.id} label="Построить план по вакансии" />
          )}
          <Link to="/plans" className={buttonVariants({ variant: 'ghost' })}>
            Все планы
          </Link>
        </CardContent>
      </Card>

      {gaps ? (
        <VacancyAssessment
          vacancy={vacancy}
          gaps={gaps}
          hasProfile={hasProfile}
          token={token}
          onUnauthorized={expire}
        />
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
