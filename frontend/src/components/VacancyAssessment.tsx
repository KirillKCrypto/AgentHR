import { Link } from 'react-router'

import type { GapAnalysisRead, VacancyRead } from '@/api/client'
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export function VacancyAssessment({
  vacancy,
  gaps,
  hasProfile,
}: {
  vacancy: VacancyRead
  gaps: GapAnalysisRead
  hasProfile: boolean
}) {
  const coverage = Math.round(gaps.coverage_all * 100)
  const confirmed =
    gaps.confirmed_readiness === null || gaps.confirmed_readiness === undefined
      ? null
      : Math.round(gaps.confirmed_readiness * 100)
  const satisfied = gaps.items.filter((item) => item.satisfied).length

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
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1">
                  <span className="text-3xl font-medium">{coverage}%</span>
                  <span className="text-sm text-muted-foreground">готовность по вакансии</span>
                  <Progress value={coverage} />
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-3xl font-medium">
                    {confirmed === null ? '—' : `${confirmed}%`}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    подтверждённая готовность
                  </span>
                  {confirmed === null ? (
                    <span className="text-xs text-muted-foreground">
                      нет подтверждённых требований
                    </span>
                  ) : (
                    <Progress value={confirmed} />
                  )}
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                {satisfied} из {gaps.items.length} требований закрыто. Коэффициент навыка —
                отношение уровня в профиле к требуемому.
              </p>
              {gaps.critical_gap_count > 0 ? (
                <p className="text-sm text-destructive">
                  {gaps.critical_gap_count} обязательных требований не закрыто.
                </p>
              ) : null}
              {gaps.unmatched_count > 0 ? (
                <p className="text-sm text-muted-foreground">
                  {gaps.unmatched_count} навык(ов) вне онтологии: показаны, но не входят в
                  готовность.
                </p>
              ) : null}
            </>
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
          <div>
            <Link
              to={`/profile?vacancy=${vacancy.id}`}
              className={buttonVariants({ variant: 'outline' })}
            >
              Открыть профиль знаний
            </Link>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Требования и уровень</CardTitle>
          <CardDescription>
            Требуется — уровень из вакансии, в профиле — ваш коэффициент, разрыв — чего не
            хватает.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {gaps.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Требований в вакансии нет.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Навык</TableHead>
                  <TableHead>Тема</TableHead>
                  <TableHead>Требуется</TableHead>
                  <TableHead>В профиле</TableHead>
                  <TableHead>Коэффициент</TableHead>
                  <TableHead>Разрыв</TableHead>
                  <TableHead>Статус</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {gaps.items.map((item) => (
                  <TableRow key={item.skill_name}>
                    <TableCell>{item.skill_name}</TableCell>
                    <TableCell>
                      {item.topic_name ?? <Badge variant="outline">вне онтологии</Badge>}
                    </TableCell>
                    <TableCell>{item.required_level}</TableCell>
                    <TableCell>{item.user_level}</TableCell>
                    <TableCell>
                      {coefficient(item.user_level, item.required_level)}%
                    </TableCell>
                    <TableCell>{item.gap}</TableCell>
                    <TableCell>
                      {item.satisfied ? (
                        <Badge>достаточно</Badge>
                      ) : (
                        <Badge variant="destructive">не хватает {item.gap}</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function coefficient(userLevel: number, requiredLevel: number): number {
  if (requiredLevel <= 0) {
    return 100
  }
  return Math.min(100, Math.round((userLevel / requiredLevel) * 100))
}
