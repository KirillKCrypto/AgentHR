import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link } from 'react-router'

import { ApiError, fetchPlan, listPlans, type PlanRead } from '@/api/client'
import { TopicTest } from '@/components/TopicTest'
import { buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { errorMessage } from '@/lib/errors'

/**
 * Тесты по темам последнего плана подготовки.
 * Показывает вопросы банка, а не отдельный фиксированный набор тем.
 */
export function PlanSkillTestsCard({
  token,
  onUnauthorized,
}: {
  token: string
  onUnauthorized: () => void
}) {
  const plansQuery = useQuery({
    queryKey: ['plans', token],
    queryFn: () => listPlans(token),
    retry: false,
  })
  const planId = plansQuery.data?.[0]?.id ?? null
  const planQuery = useQuery<PlanRead>({
    queryKey: ['plan', planId, token],
    queryFn: () => fetchPlan(planId as string, token),
    enabled: planId !== null,
    retry: false,
  })

  const error = plansQuery.error ?? planQuery.error
  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      onUnauthorized()
    }
  }, [error, onUnauthorized])

  // Карточка появляется после построения плана.
  if (!plansQuery.isPending && !plansQuery.isError && planId === null) {
    return null
  }

  return (
    <Card id="skill-assessment">
      <CardHeader>
        <CardTitle>Проверка навыков из резюме</CardTitle>
        <CardDescription>
          Тесты по темам вашего плана подготовки: 10 вопросов разной сложности, без выбора
          сложности. Сначала постройте план по профилю.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {plansQuery.isPending ? (
          <p className="text-sm text-muted-foreground">Загружаем план…</p>
        ) : plansQuery.isError ? (
          <p className="text-sm text-destructive">{errorMessage(plansQuery.error)}</p>
        ) : planId === null ? null : planQuery.isPending ? (
          <p className="text-sm text-muted-foreground">Загружаем темы плана…</p>
        ) : planQuery.isError || !planQuery.data ? (
          <p className="text-sm text-destructive">{errorMessage(planQuery.error)}</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm text-muted-foreground">
                {planQuery.data.title} · {planQuery.data.items.length} тем
              </span>
              <Link
                to={`/plans/${planQuery.data.id}`}
                className={buttonVariants({ variant: 'outline' })}
              >
                Открыть план
              </Link>
            </div>
            <div className="flex flex-col gap-4">
              {planQuery.data.items.map((item) => (
                <div key={item.topic_id} className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{item.topic_name}</span>
                    <span className="text-sm text-muted-foreground">
                      {item.current_level} → {item.target_level}
                    </span>
                  </div>
                  <TopicTest topicKey={item.topic_key} token={token} onUnauthorized={onUnauthorized} />
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
