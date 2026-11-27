import { useState } from 'react'

import type { GapAnalysisRead } from '@/api/client'
import { TopicTest } from '@/components/TopicTest'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
import { bandLabel, percent, skillStatusLabel } from '@/lib/labels'

type GapItem = GapAnalysisRead['items'][number]
type Recommendation = GapAnalysisRead['recommendations'][number]
type Blocker = GapAnalysisRead['blockers'][number]
type Confirmation = GapAnalysisRead['confirmation_queue'][number]

export function GapMetrics({ gaps }: { gaps: GapAnalysisRead }) {
  const potential = Math.round((gaps.potential_readiness ?? gaps.readiness) * 100)
  const verified =
    gaps.verified_readiness === null || gaps.verified_readiness === undefined
      ? null
      : Math.round(gaps.verified_readiness * 100)
  const evidence = Math.round(gaps.evidence_coverage * 100)
  const criticalVerified =
    gaps.critical_verified === null || gaps.critical_verified === undefined
      ? null
      : Math.round(gaps.critical_verified * 100)
  const critical =
    gaps.critical_readiness === null || gaps.critical_readiness === undefined
      ? null
      : Math.round(gaps.critical_readiness * 100)

  return (
    <>
      <div className="flex flex-col gap-2 rounded-md border bg-muted/30 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={gaps.band === 'ready' ? 'default' : 'secondary'}>
            {bandLabel(gaps.band)}
          </Badge>
          <span className="text-sm text-muted-foreground">{gaps.band_reason}</span>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <div className="flex flex-col gap-1">
          <span className="text-3xl font-medium">{verified === null ? '—' : `${verified}%`}</span>
          <span className="text-sm text-muted-foreground">подтверждено</span>
          {verified !== null ? <Progress value={verified} /> : null}
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-3xl font-medium">{potential}%</span>
          <span className="text-sm text-muted-foreground">потенциал</span>
          <Progress value={potential} />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-3xl font-medium">
            {criticalVerified === null ? '—' : `${criticalVerified}%`}
          </span>
          <span className="text-sm text-muted-foreground">обязательные подтверждены</span>
          {criticalVerified !== null ? <Progress value={criticalVerified} /> : null}
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-3xl font-medium">{evidence}%</span>
          <span className="text-sm text-muted-foreground">покрытие доказательствами</span>
          <Progress value={evidence} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
        <span>
          {gaps.satisfied_count} из {gaps.requirements_count} требований закрыто
        </span>
        {critical !== null ? <span>· потенциально критических {critical}%</span> : null}
        <span>· средний разрыв {Math.round(gaps.average_gap)} п.</span>
      </div>

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
          <TableHead>Обязательность</TableHead>
          <TableHead>Нужно</TableHead>
          <TableHead>Резюме</TableHead>
          <TableHead>Подтверждено</TableHead>
          <TableHead>Разрыв</TableHead>
          <TableHead>Статус</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.skill_name}>
            <TableCell>
              <span className="font-medium">{item.skill_name}</span>
              {item.topic_name && item.topic_name !== item.skill_name ? (
                <span className="block text-xs text-muted-foreground">{item.topic_name}</span>
              ) : null}
            </TableCell>
            <TableCell>
              <Badge variant={item.criticality === 'must_have' ? 'default' : 'outline'}>
                {item.criticality === 'must_have' ? 'обязательно' : 'желательно'}
              </Badge>
            </TableCell>
            <TableCell>{item.required_level}</TableCell>
            <TableCell>{item.self_level > 0 ? item.self_level : '—'}</TableCell>
            <TableCell>
              {item.verified_level > 0 ? item.verified_level : '—'}
              {item.evidence_type !== 'none' ? (
                <span className="block text-xs text-muted-foreground">
                  {item.evidence_type}
                </span>
              ) : null}
            </TableCell>
            <TableCell>
              {item.verified_gap > 0 ? (
                <span className="text-destructive">−{item.verified_gap}</span>
              ) : (
                <span className="text-muted-foreground">0</span>
              )}
            </TableCell>
            <TableCell>
              <SkillStatusBadge item={item} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function SkillStatusBadge({ item }: { item: GapItem }) {
  if (item.status === 'confirmed') {
    return <Badge>подтверждён</Badge>
  }
  if (item.covered_by_alternative) {
    return <Badge variant="outline">закрыто альтернативой</Badge>
  }
  if (item.status === 'partial') {
    return <Badge variant="secondary">{skillStatusLabel(item.status)}</Badge>
  }
  if (item.status === 'self_only') {
    return <Badge variant="outline">только резюме</Badge>
  }
  return <Badge variant="destructive">не проверен</Badge>
}

export function GapBlockers({ items }: { items: Blocker[] }) {
  if (items.length === 0) {
    return null
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Что блокирует готовность</CardTitle>
        <CardDescription>
          Обязательные требования, которые не закрыты подтверждёнными навыками.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {items.map((item) => (
          <div
            key={item.topic_key ?? item.skill_name}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3"
          >
            <div className="flex flex-col gap-1">
              <span className="font-medium">{item.topic_name ?? item.skill_name}</span>
              <span className="text-xs text-muted-foreground">
                подтверждено {item.verified_level} из {item.required_level}
              </span>
            </div>
            <Badge variant="destructive">не хватает {item.gap}</Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export function GapConfirmationQueue({
  items,
  token,
  onUnauthorized,
}: {
  items: Confirmation[]
  token: string
  onUnauthorized: () => void
}) {
  if (items.length === 0) {
    return null
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Что подтвердить для точного расчёта</CardTitle>
        <CardDescription>
          Навыки, которые сильнее всего уточнят подтверждённую готовность. Тест
          можно пройти прямо здесь, без плана.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {items.map((item) => (
          <ConfirmationRow
            key={item.topic_key ?? item.skill_name}
            item={item}
            token={token}
            onUnauthorized={onUnauthorized}
          />
        ))}
      </CardContent>
    </Card>
  )
}

function ConfirmationRow({
  item,
  token,
  onUnauthorized,
}: {
  item: Confirmation
  token: string
  onUnauthorized: () => void
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex flex-col gap-3 border-b pb-3 last:border-b-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{item.topic_name ?? item.skill_name}</span>
          <Badge variant={item.criticality === 'must_have' ? 'default' : 'outline'}>
            {item.criticality === 'must_have' ? 'обязательно' : 'желательно'}
          </Badge>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">+{percent(item.potential_gain)}</Badge>
          {item.topic_key ? (
            <Button
              type="button"
              size="sm"
              variant={open ? 'ghost' : 'outline'}
              onClick={() => setOpen((value) => !value)}
            >
              {open ? 'Скрыть тест' : 'Пройти тест'}
            </Button>
          ) : null}
        </div>
      </div>
      <span className="text-xs text-muted-foreground">{item.reason}</span>
      {open && item.topic_key ? (
        <TopicTest
          topicKey={item.topic_key}
          token={token}
          onUnauthorized={onUnauthorized}
        />
      ) : null}
    </div>
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
