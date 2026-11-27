import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import {
  ApiError,
  fetchPlan,
  fetchPlanProgress,
  listPlans,
  type PlanRead,
} from '@/api/client'
import { CollapsibleCard } from '@/components/CollapsibleCard'
import { TopicTest } from '@/components/TopicTest'
import { buttonVariants } from '@/components/ui/button'
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
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const plansQuery = useQuery({
    queryKey: ['plans', token],
    queryFn: () => listPlans(token),
    retry: false,
  })
  const activePlans = (plansQuery.data ?? []).filter((plan) => plan.status === 'active')
  const planId =
    selectedPlanId && activePlans.some((plan) => plan.id === selectedPlanId)
      ? selectedPlanId
      : (activePlans[0]?.id ?? null)
  const planQuery = useQuery<PlanRead>({
    queryKey: ['plan', planId, token],
    queryFn: () => fetchPlan(planId as string, token),
    enabled: planId !== null,
    retry: false,
  })
  const progressQuery = useQuery({
    queryKey: ['plan-progress', planId, token],
    queryFn: () => fetchPlanProgress(planId as string, token),
    enabled: planId !== null,
    retry: false,
  })

  const error = plansQuery.error ?? planQuery.error ?? progressQuery.error
  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      onUnauthorized()
    }
  }, [error, onUnauthorized])

  // Карточка остаётся на месте: при отсутствии плана показываем пустое состояние.
  return (
    <CollapsibleCard
      id="skill-assessment"
      title="Проверка навыков из резюме"
      description="Тесты по темам вашего плана подготовки: 10 вопросов разной сложности, без выбора сложности. Сначала постройте план по профилю."
      storageKey="profile-tests"
    >
      <div className="flex flex-col gap-4">
        {plansQuery.isPending ? (
          <p className="text-sm text-muted-foreground">Загружаем план…</p>
        ) : plansQuery.isError ? (
          <p className="text-sm text-destructive">{errorMessage(plansQuery.error)}</p>
        ) : planId === null ? (
          <p className="text-sm text-muted-foreground">
            Активного плана нет. Создайте план подготовки, чтобы пройти тесты по темам.
          </p>
        ) : planQuery.isPending ? (
          <p className="text-sm text-muted-foreground">Загружаем темы плана…</p>
        ) : planQuery.isError || !planQuery.data ? (
          <p className="text-sm text-muted-foreground">
            {planQuery.error instanceof ApiError && planQuery.error.status === 404
              ? 'План больше не актуален. Создайте новый план подготовки.'
              : errorMessage(planQuery.error)}
          </p>
        ) : (
          <>
            {activePlans.length > 1 ? (
              <div className="flex flex-wrap gap-2">
                {activePlans.map((plan) => (
                  <button
                    key={plan.id}
                    type="button"
                    onClick={() => setSelectedPlanId(plan.id)}
                    className={buttonVariants({
                      variant: plan.id === planId ? 'default' : 'outline',
                      size: 'sm',
                    })}
                  >
                    {plan.kind === 'vacancy' ? 'По вакансии' : 'Общий'}
                    {plan.vacancy_title ? `: ${plan.vacancy_title}` : ''}
                  </button>
                ))}
              </div>
            ) : null}
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
              {planQuery.data.items.map((item) => {
                const progress = progressQuery.data?.items.find(
                  (entry) => entry.topic_id === item.topic_id,
                )
                return (
                  <div key={item.topic_id} className="flex flex-col gap-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{item.topic_name}</span>
                      <span className="text-sm text-muted-foreground">
                        {progress?.test_level ?? 0} → {progress?.target_level ?? item.target_level}
                      </span>
                    </div>
                    <TopicTest
                      topicKey={item.topic_key}
                      token={token}
                      onUnauthorized={onUnauthorized}
                    />
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>
    </CollapsibleCard>
  )
}
