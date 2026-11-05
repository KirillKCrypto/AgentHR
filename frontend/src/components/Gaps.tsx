import type { GapAnalysisRead } from '@/api/client'
import { Badge } from '@/components/ui/badge'
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

type GapItem = GapAnalysisRead['items'][number]
type Recommendation = GapAnalysisRead['recommendations'][number]

export function GapMetrics({ gaps }: { gaps: GapAnalysisRead }) {
  const coverage = Math.round(gaps.coverage_all * 100)
  const critical =
    gaps.critical_readiness === null || gaps.critical_readiness === undefined
      ? null
      : Math.round(gaps.critical_readiness * 100)

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1">
          <span className="text-3xl font-medium">{coverage}%</span>
          <span className="text-sm text-muted-foreground">готовность по вакансии</span>
          <Progress value={coverage} />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-3xl font-medium">
            {critical === null ? '—' : `${critical}%`}
          </span>
          <span className="text-sm text-muted-foreground">обязательные требования</span>
          {critical === null ? (
            <span className="text-xs text-muted-foreground">нет must_have</span>
          ) : (
            <Progress value={critical} />
          )}
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-3xl font-medium">{Math.round(gaps.average_gap)}</span>
          <span className="text-sm text-muted-foreground">средний разрыв, пункты</span>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">
        {gaps.satisfied_count} из {gaps.requirements_count} требований закрыто.
      </p>
      {gaps.critical_gap_count > 0 ? (
        <p className="text-sm text-destructive">
          {gaps.critical_gap_count} обязательных требований не закрыто.
        </p>
      ) : null}
      {gaps.unmatched_count > 0 ? (
        <p className="text-sm text-muted-foreground">
          {gaps.unmatched_count} навык(ов) вне онтологии: показаны, но не входят в готовность.
        </p>
      ) : null}
    </>
  )
}

export function GapTable({ items }: { items: GapItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">Требований в вакансии нет.</p>
  }

  return (
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
        {items.map((item) => (
          <TableRow key={item.skill_name}>
            <TableCell>{item.skill_name}</TableCell>
            <TableCell>
              {item.topic_name ?? <Badge variant="outline">вне онтологии</Badge>}
            </TableCell>
            <TableCell>{item.required_level}</TableCell>
            <TableCell>{item.user_level}</TableCell>
            <TableCell>{coefficient(item.user_level, item.required_level)}%</TableCell>
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
  )
}

export function GapRecommendations({ items }: { items: Recommendation[] }) {
  if (items.length === 0) {
    return null
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Что подтянуть в первую очередь</CardTitle>
        <CardDescription>
          Отсортировано по критичности, весу требования и размеру разрыва.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {items.map((item) => (
          <div
            key={item.topic_key ?? item.skill_name}
            className="flex flex-col gap-1 border-b pb-3 last:border-b-0 last:pb-0"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">{item.topic_name ?? item.skill_name}</span>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={item.criticality === 'must_have' ? 'default' : 'outline'}>
                  {item.criticality === 'must_have' ? 'обязательно' : 'желательно'}
                </Badge>
                <Badge variant="destructive">не хватает {item.gap}</Badge>
              </div>
            </div>
            <span className="text-sm text-muted-foreground">
              в профиле {item.user_level} из {item.required_level} · приоритет{' '}
              {Math.round(item.priority * 100)}%
            </span>
            <span className="text-xs text-muted-foreground">{item.reason}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function coefficient(userLevel: number, requiredLevel: number): number {
  if (requiredLevel <= 0) {
    return 100
  }
  return Math.min(100, Math.round((userLevel / requiredLevel) * 100))
}
