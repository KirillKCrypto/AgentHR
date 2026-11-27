import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link } from 'react-router'

import {
  ApiError,
  fetchDashboard,
  fetchProfile,
  listPlans,
  type DashboardRead,
  type PlanSummary,
  type ProfileRead,
} from '@/api/client'
import { buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { errorMessage } from '@/lib/errors'
import { useAuthToken } from '@/lib/useAuthToken'

export default function ProfileOverviewPage() {
  const { token, expire } = useAuthToken()

  const profileQuery = useQuery<ProfileRead>({
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
  const dashboardQuery = useQuery<DashboardRead>({
    queryKey: ['dashboard', null, token],
    queryFn: () => fetchDashboard(token as string),
    enabled: token !== null,
    retry: false,
  })

  const error = profileQuery.error ?? plansQuery.error ?? dashboardQuery.error
  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      expire()
    }
  }, [error, expire])

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Профиль</CardTitle>
          <CardDescription>Войдите, чтобы открыть профиль.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (profileQuery.isPending || plansQuery.isPending || dashboardQuery.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Профиль</CardTitle>
          <CardDescription>Собираем данные…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Профиль</CardTitle>
          <CardDescription>{errorMessage(profileQuery.error)}</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const profile = profileQuery.data
  const plans = plansQuery.data ?? []
  const activePlans = plans.filter((plan) => plan.status === 'active')
  const vacancyPlans = activePlans.filter((plan) => plan.kind === 'vacancy')
  const generalPlans = activePlans.filter((plan) => plan.kind === 'general')
  const dashboard = dashboardQuery.data

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Тем в профиле"
          value={profile.topics.length}
          hint={`${profile.topics.filter((topic) => topic.verified_level !== null).length} подтверждено`}
        />
        <StatCard
          label="Активных планов"
          value={activePlans.length}
          hint={`${vacancyPlans.length} по вакансиям · ${generalPlans.length} общий`}
        />
        <StatCard
          label="Пройдено тестов"
          value={dashboard?.tests.completed_count ?? 0}
          hint={
            dashboard?.tests.average_level === null ||
            dashboard?.tests.average_level === undefined
              ? 'Средний балл пока не считается'
              : `Средний уровень ${Math.round(dashboard.tests.average_level)}`
          }
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Разделы профиля</CardTitle>
          <CardDescription>Быстрый переход к нужному разделу.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Link to="/profile/resumes" className={buttonVariants({ variant: 'outline' })}>
            Резюме
          </Link>
          <Link to="/profile/skills" className={buttonVariants({ variant: 'outline' })}>
            Навыки и разрывы
          </Link>
          <Link to="/profile/tests" className={buttonVariants({ variant: 'outline' })}>
            Тесты по темам
          </Link>
          <Link to="/plans" className={buttonVariants()}>
            Все планы
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Активные планы</CardTitle>
          <CardDescription>
            Общий план и планы под конкретные вакансии.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {activePlans.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Активных планов нет. Постройте общий план или план по вакансии.
            </p>
          ) : (
            activePlans.map((plan) => (
              <Link
                key={plan.id}
                to={`/plans/${plan.id}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 transition-colors hover:bg-muted/50"
              >
                <div className="flex flex-col gap-1">
                  <span className="text-sm font-medium">{plan.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {plan.kind === 'vacancy' ? 'По вакансии' : 'Общий'} ·{' '}
                    {plan.topic_count} тем
                  </span>
                </div>
              </Link>
            ))
          )}
          <div className="flex flex-wrap gap-2">
            <Link to="/plans" className={buttonVariants({ variant: 'outline' })}>
              Открыть планы
            </Link>
            <Link to="/vacancies/new" className={buttonVariants({ variant: 'outline' })}>
              Проверить вакансию
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string
  value: number
  hint: string
}) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-1 pt-4">
        <span className="text-3xl font-medium">{value}</span>
        <span className="text-sm font-medium">{label}</span>
        <span className="text-xs text-muted-foreground">{hint}</span>
      </CardContent>
    </Card>
  )
}
