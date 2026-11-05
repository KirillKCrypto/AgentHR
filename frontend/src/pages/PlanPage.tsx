import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError, fetchPlan, type PlanRead } from '@/api/client'
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
    return (
      <Card>
        <CardHeader>
          <CardTitle>План подготовки</CardTitle>
          <CardDescription>{errorMessage(planQuery.error)}</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/profile" className={buttonVariants({ variant: 'outline' })}>
            К профилю
          </Link>
        </CardContent>
      </Card>
    )
  }

  const plan = planQuery.data

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{plan.title}</CardTitle>
          <CardDescription>
            {plan.items.length} тем из вашего резюме. Сначала самые сильные навыки.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {plan.vacancy_id ? (
            <Link
              to={`/vacancies/${plan.vacancy_id}`}
              className={buttonVariants({ variant: 'outline' })}
            >
              Открыть вакансию
            </Link>
          ) : null}
          <Link to="/profile" className={buttonVariants({ variant: 'outline' })}>
            Открыть профиль
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Темы</CardTitle>
          <CardDescription>
            Текущий уровень, цель и причина выбора темы в план.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {plan.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              В плане нет тем — загрузите резюме и постройте план заново.
            </p>
          ) : (
            plan.items.map((item, index) => (
              <div key={item.topic_id} className="flex flex-col gap-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm text-muted-foreground">{index + 1}.</span>
                    <span className="font-medium">{item.topic_name}</span>
                    {item.category ? (
                      <Badge variant="outline">{item.category}</Badge>
                    ) : null}
                  </div>
                  <span className="text-sm tabular-nums">
                    {item.current_level} → {item.target_level}
                  </span>
                </div>
                <Progress value={item.current_level} />
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>приоритет {Math.round(item.priority)}</span>
                  <span>·</span>
                  <span>вопросов в банке: {item.question_count}</span>
                  <span>·</span>
                  <span>уверенность {Math.round(item.confidence * 100)}%</span>
                  <span>·</span>
                  <span>{item.reason}</span>
                </div>
                <TopicTest topicKey={item.topic_key} token={token} />
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}

