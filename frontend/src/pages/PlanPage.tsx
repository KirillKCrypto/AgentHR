import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError, fetchPlan, fetchPlanProgress, type PlanRead } from '@/api/client'
import { TopicTest } from '@/components/TopicTest'
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
import { skillStatusLabel } from '@/lib/labels'
import { useAuthToken } from '@/lib/useAuthToken'

export default function PlanPage() {
  const { planId } = useParams<{ planId: string }>()
  const { token, expire } = useAuthToken()

  const planQuery = useQuery<PlanRead>({
    queryKey: ['plan', planId, token],
    queryFn: () => fetchPlan(planId as string, token as string),
    enabled: token !== null && Boolean(planId),
    retry: false,
  })

  const progressQuery = useQuery({
    queryKey: ['plan-progress', planId, token],
    queryFn: () => fetchPlanProgress(planId as string, token as string),
    enabled: token !== null && Boolean(planId),
    retry: false,
  })

  useEffect(() => {
    if (planQuery.error instanceof ApiError && planQuery.error.status === 401) {
      expire()
    }
  }, [planQuery.error, expire])

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>План подготовки</CardTitle>
          <CardDescription>Войдите, чтобы открыть план.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (planQuery.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>План подготовки</CardTitle>
          <CardDescription>Загружаем план…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (planQuery.isError || !planQuery.data) {
    const planIsArchived =
      planQuery.error instanceof ApiError && planQuery.error.status === 404
    return (
      <Card>
        <CardHeader>
          <CardTitle>План подготовки</CardTitle>
          <CardDescription>
            {planIsArchived
              ? 'Этот план больше не актуален: после смены резюме он архивирован. Новый план строится автоматически.'
              : errorMessage(planQuery.error)}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Link to="/" className={buttonVariants()}>
            На дашборд
          </Link>
          <Link to="/profile/skills" className={buttonVariants({ variant: 'outline' })}>
            К профилю
          </Link>
        </CardContent>
      </Card>
    )
  }

  const plan = planQuery.data
  const progressByTopic = new Map(
    (progressQuery.data?.items ?? []).map((item) => [item.topic_id, item]),
  )

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={plan.kind === 'vacancy' ? 'default' : 'outline'}>
              {plan.kind === 'vacancy' ? 'План по вакансии' : 'Общий план'}
            </Badge>
            <CardTitle>{plan.title}</CardTitle>
          </div>
          <CardDescription>
            {plan.resume_title ? `Резюме: ${plan.resume_title}. ` : ''}
            {plan.items.length} тем: сначала разрывы вакансии, слабые ответы и
            незатронутые темы.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {progressQuery.data ? (
            <div className="flex w-full flex-col gap-1">
              <span className="text-sm text-muted-foreground">
                Прогресс плана: {Math.round(progressQuery.data.progress * 100)}% ·
                тестов {progressQuery.data.tests_completed} из{' '}
                {progressQuery.data.topics_total} · зачтено{' '}
                {progressQuery.data.tests_passed} · закрыто{' '}
                {progressQuery.data.completed_count} тем
              </span>
              <Progress value={Math.round(progressQuery.data.progress * 100)} />
              <span className="text-xs text-muted-foreground">
                {progressQuery.data.average_score !== null &&
                progressQuery.data.average_score !== undefined
                  ? `средний балл тестов ${Math.round(progressQuery.data.average_score * 100)}% · `
                  : ''}
                {progressQuery.data.next_topic_name
                  ? `следующая тема: ${progressQuery.data.next_topic_name}`
                  : 'все темы пройдены'}
              </span>
            </div>
          ) : null}
          <Link to="/plans" className={buttonVariants({ variant: 'ghost' })}>
            Все планы
          </Link>
          {plan.vacancy_id ? (
            <Link
              to={`/vacancies/${plan.vacancy_id}`}
              className={buttonVariants({ variant: 'outline' })}
            >
              Открыть вакансию
            </Link>
          ) : null}
          <Link to="/profile/skills" className={buttonVariants({ variant: 'outline' })}>
            Открыть профиль
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Темы</CardTitle>
          <CardDescription>
            Подтверждённый тестом уровень, цель и причина выбора темы в план.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {plan.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              В плане нет тем — загрузите резюме и постройте план заново.
            </p>
          ) : (
            plan.items.map((item, index) => {
              const progress = progressByTopic.get(item.topic_id)
              const level = progress?.test_level ?? 0
              const target = progress?.target_level ?? item.target_level
              const status = progress?.status ?? 'not_tested'
              return (
                <div key={item.topic_id} className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm text-muted-foreground">{index + 1}.</span>
                      <span className="font-medium">{item.topic_name}</span>
                      {item.category ? (
                        <Badge variant="outline">{item.category}</Badge>
                      ) : null}
                      {item.criticality === 'must_have' ? (
                        <Badge>обязательно</Badge>
                      ) : null}
                      <Badge variant={status === 'confirmed' ? 'default' : 'secondary'}>
                        {skillStatusLabel(status)}
                      </Badge>
                    </div>
                    <span className="text-sm tabular-nums">
                      {level} → {target}
                    </span>
                  </div>
                  <Progress value={level} />
                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>приоритет {Math.round(item.priority)}</span>
                    <span>·</span>
                    <span>вопросов в банке: {item.question_count}</span>
                    {progress ? (
                      <>
                        <span>·</span>
                        <span>
                          попыток: {progress.attempts_count} · балл{' '}
                          {Math.round((progress.test_score ?? 0) * 100)}%
                        </span>
                      </>
                    ) : null}
                    <span>·</span>
                    <span>{item.reason}</span>
                  </div>
                  <TopicTest topicKey={item.topic_key} token={token} onUnauthorized={expire} />
                </div>
              )
            })
          )}
        </CardContent>
      </Card>
    </div>
  )
}

