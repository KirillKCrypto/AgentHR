import { useQueries, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import {
  ApiError,
  fetchPlanProgress,
  listPlans,
  type PlanSummary,
} from '@/api/client'
import { CreatePlanButton } from '@/components/CreatePlanButton'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { errorMessage } from '@/lib/errors'
import { formatDate } from '@/lib/labels'
import { useAuthToken } from '@/lib/useAuthToken'

type Tab = 'vacancy' | 'general'

export default function PlansPage() {
  const { token, expire } = useAuthToken()
  const [tab, setTab] = useState<Tab>('vacancy')

  const plansQuery = useQuery<PlanSummary[]>({
    queryKey: ['plans', token],
    queryFn: () => listPlans(token as string),
    enabled: token !== null,
    retry: false,
  })

  useEffect(() => {
    if (plansQuery.error instanceof ApiError && plansQuery.error.status === 401) {
      expire()
    }
  }, [plansQuery.error, expire])

  const plans = plansQuery.data ?? []
  const activePlans = plans.filter((plan) => plan.status === 'active')
  const progressQueries = useQueries({
    queries: activePlans.map((plan) => ({
      queryKey: ['plan-progress', plan.id, token],
      queryFn: () => fetchPlanProgress(plan.id, token as string),
      enabled: token !== null,
      retry: false,
    })),
  })
  const progressById = new Map(
    activePlans.map((plan, index) => [plan.id, progressQueries[index]?.data]),
  )

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Планы подготовки</CardTitle>
          <CardDescription>Войдите, чтобы открыть планы.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (plansQuery.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Планы подготовки</CardTitle>
          <CardDescription>Загружаем планы…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (plansQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Планы подготовки</CardTitle>
          <CardDescription>{errorMessage(plansQuery.error)}</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const visible = plans.filter((plan) => plan.kind === tab)

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Планы подготовки</CardTitle>
          <CardDescription>
            Планы по конкретным вакансиям и общий план по профилю.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setTab('vacancy')}
            className={buttonVariants({
              variant: tab === 'vacancy' ? 'default' : 'outline',
              size: 'sm',
            })}
          >
            По вакансиям
          </button>
          <button
            type="button"
            onClick={() => setTab('general')}
            className={buttonVariants({
              variant: tab === 'general' ? 'default' : 'outline',
              size: 'sm',
            })}
          >
            Общий
          </button>
          {tab === 'general' ? <CreatePlanButton label="Построить общий план" /> : null}
          <Link to="/vacancies/new" className={buttonVariants({ variant: 'outline' })}>
            Новая вакансия
          </Link>
        </CardContent>
      </Card>

      {visible.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>
              {tab === 'vacancy' ? 'Планов по вакансиям пока нет' : 'Общего плана пока нет'}
            </CardTitle>
            <CardDescription>
              {tab === 'vacancy'
                ? 'Загрузите вакансию и постройте план — он появится здесь.'
                : 'Постройте общий план по профилю знаний.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {tab === 'vacancy' ? (
              <Link to="/vacancies/new" className={buttonVariants()}>
                Проверить вакансию
              </Link>
            ) : (
              <CreatePlanButton label="Построить общий план" />
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {visible.map((plan) => {
            const progress = progressById.get(plan.id)
            return (
              <Card key={plan.id}>
                <CardHeader>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={plan.kind === 'vacancy' ? 'default' : 'outline'}>
                      {plan.kind === 'vacancy' ? 'По вакансии' : 'Общий'}
                    </Badge>
                    {plan.status !== 'active' ? (
                      <Badge variant="secondary">{plan.status}</Badge>
                    ) : null}
                  </div>
                  <CardTitle>{plan.title}</CardTitle>
                  <CardDescription>
                    {plan.vacancy_title ? `${plan.vacancy_title} · ` : ''}
                    {plan.topic_count} тем
                    {plan.created_at ? ` · ${formatDate(plan.created_at)}` : ''}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  {plan.status === 'active' && progress ? (
                    <>
                      <div className="flex items-end justify-between gap-2">
                        <span className="text-2xl font-medium">
                          {Math.round(progress.progress * 100)}%
                        </span>
                        <span className="text-xs text-muted-foreground">
                          тестов {progress.tests_completed} · закрыто{' '}
                          {progress.completed_count}
                        </span>
                      </div>
                      <Progress value={Math.round(progress.progress * 100)} />
                    </>
                  ) : null}
                  <Link to={`/plans/${plan.id}`} className={buttonVariants({ variant: 'outline' })}>
                    Открыть план
                  </Link>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
