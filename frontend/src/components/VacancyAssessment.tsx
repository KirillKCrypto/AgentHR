import { Link } from 'react-router'

import type { GapAnalysisRead, VacancyRead } from '@/api/client'
import { CreatePlanButton } from '@/components/CreatePlanButton'
import { GapMetrics, GapRecommendations, GapTable } from '@/components/Gaps'
import { buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export function VacancyAssessment({
  vacancy,
  gaps,
  hasProfile,
}: {
  vacancy: VacancyRead
  gaps: GapAnalysisRead
  hasProfile: boolean
}) {
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Оценка вакансии</CardTitle>
          <CardDescription>
            {vacancy.title ?? 'Без названия'}
            {vacancy.company ? ` · ${vacancy.company}` : ''}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {hasProfile ? (
            <GapMetrics gaps={gaps} />
          ) : (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                Профиль пуст — сравнить требования не с чем. Загрузите резюме, и оценка
                появится на этой странице.
              </p>
              <div>
                <Link to="/profile" className={buttonVariants()}>
                  Загрузить резюме
                </Link>
              </div>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={`/profile?vacancy=${vacancy.id}`}
              className={buttonVariants({ variant: 'outline' })}
            >
              Открыть профиль знаний
            </Link>
            <CreatePlanButton vacancyId={vacancy.id} />
          </div>
        </CardContent>
      </Card>

      {hasProfile ? <GapRecommendations items={gaps.recommendations} /> : null}

      <Card>
        <CardHeader>
          <CardTitle>Требования и уровень</CardTitle>
          <CardDescription>
            Требуется — уровень из вакансии, в профиле — ваш коэффициент, разрыв — чего не
            хватает.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <GapTable items={gaps.items} />
        </CardContent>
      </Card>
    </div>
  )
}
