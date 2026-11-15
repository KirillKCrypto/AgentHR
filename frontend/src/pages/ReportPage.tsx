import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router'

import {
  ApiError,
  fetchInterview,
  fetchInterviewReport,
  type InterviewRead,
  type InterviewReportRead,
  type InterviewReportTopicRead,
} from '@/api/client'
import { CreatePlanButton } from '@/components/CreatePlanButton'
import { StartInterviewButton } from '@/components/StartInterviewButton'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
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

export default function ReportPage() {
  const { reportId } = useParams<{ reportId: string }>()
  const { token, expire } = useAuthToken()

  const interviewQuery = useQuery<InterviewRead>({
    queryKey: ['interview', reportId, token],
    queryFn: () => fetchInterview(reportId as string, token as string),
    enabled: token !== null && Boolean(reportId),
    retry: false,
  })
  const reportQuery = useQuery<InterviewReportRead>({
    queryKey: ['interview-report', reportId, token],
    queryFn: () => fetchInterviewReport(reportId as string, token as string),
    enabled: token !== null && Boolean(reportId),
    retry: false,
  })

  const error = interviewQuery.error ?? reportQuery.error
  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      expire()
    }
  }, [error, expire])

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Отчёт</CardTitle>
          <CardDescription>Войдите, чтобы открыть отчёт.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (interviewQuery.isPending || reportQuery.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Отчёт</CardTitle>
          <CardDescription>Собираем результаты интервью…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (interviewQuery.isError || reportQuery.isError || !reportQuery.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Отчёт недоступен</CardTitle>
          <CardDescription>{errorMessage(error)}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={() => void reportQuery.refetch()}>
            Повторить
          </Button>
        </CardContent>
      </Card>
    )
  }

  const report = reportQuery.data
  const interview = interviewQuery.data
  const answered = (interview?.turns ?? []).filter(
    (turn) => turn.status === 'answered',
  )

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{report.vacancy_title ?? interview?.title ?? 'Отчёт интервью'}</CardTitle>
          <CardDescription>
            {report.finished_at ? formatDate(report.finished_at) : '—'} · отвечено{' '}
            {report.answered_count} из {report.question_count}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-end gap-4">
            <span className="text-5xl font-medium">{report.level ?? 0}</span>
            <div className="flex flex-col gap-1">
              <span className="text-sm text-muted-foreground">итоговый уровень</span>
              <Badge variant="outline">
                {Math.round(report.score ?? 0)}/100 по сложности
              </Badge>
            </div>
            {typeof report.delta === 'number' ? (
              <Badge variant={report.delta >= 0 ? 'default' : 'destructive'}>
                {report.delta >= 0 ? '+' : ''}
                {report.delta} к прошлому интервью
              </Badge>
            ) : null}
          </div>
          <Progress value={Math.round(report.score ?? 0)} />
          <div className="flex flex-wrap gap-2">
            {report.vacancy_id ? (
              <StartInterviewButton vacancyId={report.vacancy_id} />
            ) : null}
            {report.vacancy_id ? (
              <CreatePlanButton vacancyId={report.vacancy_id} label="План по слабым темам" />
            ) : null}
            {report.vacancy_id ? (
              <Link
                to={`/vacancies/${report.vacancy_id}`}
                className={buttonVariants({ variant: 'outline' })}
              >
                К вакансии
              </Link>
            ) : null}
            <Link to="/" className={buttonVariants({ variant: 'ghost' })}>
              На дашборд
            </Link>
          </div>
        </CardContent>
      </Card>

      {Object.keys(report.dimensions).length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Разбор по рубрике</CardTitle>
            <CardDescription>
              Средние значения по отвеченным вопросам.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3">
            <Dimension
              label="Верность"
              value={report.dimensions.correctness}
              max={50}
            />
            <Dimension
              label="Покрытие"
              value={report.dimensions.coverage}
              max={30}
            />
            <Dimension label="Глубина" value={report.dimensions.depth} max={20} />
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <ReportTopics
          title="Сильные темы"
          items={report.strengths}
          empty="Пока нет тем с оценкой 70 и выше."
        />
        <ReportTopics
          title="Что подтянуть"
          items={report.improvements}
          empty="Слабых тем нет."
          showMissed
        />
        <ReportTopics
          title="Не затронуто"
          items={report.untouched}
          empty="Все темы вакансии были затронуты."
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Разбор вопросов</CardTitle>
          <CardDescription>
            Ответы, оценки и рекомендации по каждому вопросу.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {answered.length === 0 ? (
            <p className="text-sm text-muted-foreground">Ответов пока нет.</p>
          ) : (
            answered.map((turn) => <ReportTurn key={turn.id} turn={turn} />)
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function Dimension({
  label,
  value,
  max,
}: {
  label: string
  value: number | undefined
  max: number
}) {
  const score = value ?? 0
  return (
    <div className="flex flex-col gap-1">
      <span className="text-2xl font-medium">
        {score}
        <span className="text-sm text-muted-foreground">/{max}</span>
      </span>
      <span className="text-sm text-muted-foreground">{label}</span>
      <Progress value={Math.round((score / max) * 100)} />
    </div>
  )
}

function ReportTopics({
  title,
  items,
  empty,
  showMissed = false,
}: {
  title: string
  items: InterviewReportTopicRead[]
  empty: string
  showMissed?: boolean
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{empty}</p>
        ) : (
          items.map((item) => (
            <div key={item.topic_key} className="flex flex-col gap-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm">{item.topic_name}</span>
                {typeof item.score === 'number' ? (
                  <Badge variant={item.score >= 70 ? 'default' : 'destructive'}>
                    {Math.round(item.score)}/100
                  </Badge>
                ) : (
                  <Badge variant="outline">не затронуто</Badge>
                )}
              </div>
              {showMissed && item.missed_points.length > 0 ? (
                <span className="text-xs text-muted-foreground">
                  Упущено: {item.missed_points.join('; ')}
                </span>
              ) : null}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}

function ReportTurn({ turn }: { turn: InterviewRead['turns'][number] }) {
  return (
    <div className="flex flex-col gap-2 border-b pb-4 last:border-b-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">
          {turn.position}. {turn.topic_name}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          {turn.kind === 'follow_up' ? (
            <Badge variant="secondary">уточнение</Badge>
          ) : null}
          <Badge variant={(turn.score ?? 0) >= 70 ? 'default' : 'destructive'}>
            {turn.score ?? 0}/100
          </Badge>
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">Вопрос</span>
        <span className="text-sm">{turn.question_text}</span>
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">Ответ</span>
        <span className="text-sm">{turn.answer_text ?? '—'}</span>
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">Анализ</span>
        <span className="text-sm">{turn.feedback ?? '—'}</span>
        {typeof turn.score_breakdown?.correctness === 'number' ? (
          <span className="text-xs text-muted-foreground">
            верность {Number(turn.score_breakdown.correctness)}/50 · покрытие{' '}
            {Number(turn.score_breakdown.coverage ?? 0)}/30 · глубина{' '}
            {Number(turn.score_breakdown.depth ?? 0)}/20
          </span>
        ) : null}
      </div>
      {turn.missed_points.length > 0 ? (
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium">Упущено</span>
          <span className="text-xs text-muted-foreground">
            {turn.missed_points.join('; ')}
          </span>
        </div>
      ) : null}
    </div>
  )
}
