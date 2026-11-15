import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import {
  ApiError,
  answerInterview,
  fetchInterview,
  fetchInterviewReport,
  streamInterviewAnswer,
  type InterviewRead,
  type InterviewReportRead,
  type InterviewReportTopicRead,
  type InterviewTurnRead,
} from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { StartInterviewButton } from '@/components/StartInterviewButton'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import { useAuthToken } from '@/lib/useAuthToken'

export default function InterviewPage() {
  const { interviewId } = useParams<{ interviewId: string }>()
  const { token, expire } = useAuthToken()
  const [session, setSession] = useState<InterviewRead | null>(null)
  const [answer, setAnswer] = useState('')
  const [streamedFeedback, setStreamedFeedback] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const interviewQuery = useQuery<InterviewRead>({
    queryKey: ['interview', interviewId, token],
    queryFn: () => fetchInterview(interviewId as string, token as string),
    enabled: token !== null && Boolean(interviewId),
    retry: false,
  })

  const completed = session?.status === 'completed'

  const reportQuery = useQuery<InterviewReportRead>({
    queryKey: ['interview-report', interviewId, token],
    queryFn: () => fetchInterviewReport(interviewId as string, token as string),
    enabled: token !== null && Boolean(interviewId) && completed,
    retry: false,
  })

  useEffect(() => {
    if (interviewQuery.error instanceof ApiError && interviewQuery.error.status === 401) {
      expire()
    }
  }, [interviewQuery.error, expire])

  useEffect(() => {
    if (interviewQuery.data && session === null) {
      setSession(interviewQuery.data)
    }
  }, [interviewQuery.data, session])

  useEffect(() => {
    // Новый URL — новое интервью: не показываем состояние предыдущего.
    setSession(null)
    setAnswer('')
    setStreamedFeedback('')
    setError(null)
  }, [interviewId])

  const currentTurn = session?.turns.find((turn) => turn.status === 'pending') ?? null

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (token === null || session === null || currentTurn === null) {
      return
    }
    const text = answer.trim()
    if (text.length < 3) {
      setError('Напишите ответ подробнее.')
      return
    }

    setBusy(true)
    setError(null)
    setStreamedFeedback('')
    let evaluated = false

    try {
      await streamInterviewAnswer(
        session.id,
        currentTurn.id,
        text,
        token,
        (name, data) => {
          if (name === 'evaluation') {
            evaluated = true
            setStreamedFeedback('')
          } else if (name === 'token') {
            const chunk = typeof data.text === 'string' ? data.text : ''
            setStreamedFeedback((current) => current + chunk)
          } else if (name === 'done') {
            const updated = data.session as InterviewRead
            setSession(updated)
            setAnswer('')
            // Фидбек уже перенесён в разбор предыдущего вопроса.
            setStreamedFeedback('')
          }
        },
      )
    } catch (value) {
      if (value instanceof ApiError && value.status === 401) {
        expire()
        return
      }
      if (!evaluated) {
        try {
          const fallback = await answerInterview(session.id, currentTurn.id, text, token)
          setSession(fallback.session)
          setStreamedFeedback(fallback.turn.feedback ?? '')
          setAnswer('')
        } catch (fallbackError) {
          setError(errorMessage(fallbackError))
        }
      } else {
        setError('Фидбек прервался. Обновите страницу — оценка уже сохранена.')
      }
    } finally {
      setBusy(false)
    }
  }

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Интервью</CardTitle>
          <CardDescription>Войдите, чтобы пройти интервью.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (interviewQuery.isPending && session === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Интервью</CardTitle>
          <CardDescription>Загружаем вопросы…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (!session) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Интервью</CardTitle>
          <CardDescription>{errorMessage(interviewQuery.error)}</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/profile" className={buttonVariants({ variant: 'outline' })}>
            К профилю
          </Link>
        </CardContent>
      </Card>
    )
  }

  const answered = session.turns.filter((turn) => turn.status === 'answered')
  const totalQuestions = session.max_questions || session.question_count
  const progress = totalQuestions
    ? Math.round((answered.length / totalQuestions) * 100)
    : 0

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{session.title || 'Тренировочное интервью'}</CardTitle>
          <CardDescription>
            Отвечено {answered.length} из {totalQuestions}. Интервью можно проходить
            повторно.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Progress value={completed ? 100 : progress} />
          {session.vacancy_id ? (
            <Link
              to={`/vacancies/${session.vacancy_id}`}
              className="text-sm underline underline-offset-4"
            >
              Вакансия: {session.vacancy_title ?? 'открыть'}
            </Link>
          ) : null}
          {completed ? (
            <div className="flex flex-wrap items-end gap-4">
              <span className="text-3xl font-medium">{session.level ?? 0}</span>
              <span className="text-sm text-muted-foreground">итоговый уровень</span>
              <Badge variant="outline">
                {Math.round(session.score ?? 0)}% по сложности
              </Badge>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {answered.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Предыдущие вопросы</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {answered.map((turn) => (
              <AnsweredTurn key={turn.id} turn={turn} />
            ))}
          </CardContent>
        </Card>
      ) : null}

      {completed ? (
        <Card>
          <CardHeader>
            <CardTitle>Итоги интервью</CardTitle>
            <CardDescription>
              Сильные темы, что подтянуть и какие темы вакансии остались незатронутыми.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {reportQuery.isPending ? (
              <p className="text-sm text-muted-foreground">Собираем итоги…</p>
            ) : reportQuery.isError || !reportQuery.data ? (
              <p className="text-sm text-destructive">
                {errorMessage(reportQuery.error)}
              </p>
            ) : (
              <>
                <ReportBlock
                  title="Сильные темы"
                  items={reportQuery.data.strengths}
                  empty="Пока нет тем с оценкой 70 и выше."
                />
                <ReportBlock
                  title="Что подтянуть"
                  items={reportQuery.data.improvements}
                  empty="Слабых тем нет."
                  showMissed
                />
                {session.vacancy_id ? (
                  <ReportBlock
                    title="Не затронуто в этом интервью"
                    items={reportQuery.data.untouched}
                    empty="Все темы вакансии были затронуты."
                  />
                ) : null}
              </>
            )}
          </CardContent>
        </Card>
      ) : null}

      {completed ? (
        <Card>
          <CardHeader>
            <CardTitle>Интервью завершено</CardTitle>
            <CardDescription>
              Результат сохранён в профиле. Слабые темы подсвечены в разборе.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Link to={`/reports/${session.id}`} className={buttonVariants()}>
              Открыть полный отчёт
            </Link>
            <Link to="/profile" className={buttonVariants({ variant: 'outline' })}>
              Открыть профиль
            </Link>
            {session.vacancy_id ? (
              <StartInterviewButton vacancyId={session.vacancy_id} />
            ) : null}
            <Link to="/" className={buttonVariants({ variant: 'outline' })}>
              На дашборд
            </Link>
          </CardContent>
        </Card>
      ) : currentTurn ? (
        <Card>
          <CardHeader>
            <CardTitle>
              Вопрос {currentTurn.position}: {currentTurn.topic_name}
              {currentTurn.kind === 'follow_up' ? (
                <Badge variant="secondary" className="ml-2">
                  уточнение
                </Badge>
              ) : null}
            </CardTitle>
            <CardDescription>
              Сложность {currentTurn.difficulty}/5. Ответьте текстом, интервьюер оценит
              полноту.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
              <div className="flex flex-col gap-1">
                <p className="text-sm font-medium">Вопрос</p>
                <p className="text-sm">{currentTurn.question_text}</p>
                {currentTurn.context ? (
                  <p className="text-xs text-muted-foreground">
                    Требование вакансии: {currentTurn.context}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-col gap-1">
                <p className="text-sm font-medium">Ответ</p>
                <Textarea
                  rows={6}
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                  placeholder="Определения, примеры, trade-offs."
                />
              </div>
              {streamedFeedback ? (
                <div className="flex flex-col gap-1 rounded-md border bg-muted/40 p-3 text-sm">
                  <span className="font-medium">Анализ</span>
                  <span>
                    {streamedFeedback}
                    {busy ? <span className="animate-pulse">▍</span> : null}
                  </span>
                </div>
              ) : null}
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <div>
                <Button type="submit" disabled={busy}>
                  {busy ? 'Интервьюер оценивает…' : 'Ответить'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

function ReportBlock({
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
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium">{title}</span>
      {items.length === 0 ? (
        <span className="text-sm text-muted-foreground">{empty}</span>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((item) => (
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
          ))}
        </div>
      )}
    </div>
  )
}

function AnsweredTurn({ turn }: { turn: InterviewTurnRead }) {
  return (
    <div className="flex flex-col gap-2 border-b pb-4 last:border-b-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">
          {turn.position}. {turn.topic_name}
        </span>
        <Badge variant={(turn.score ?? 0) >= 70 ? 'default' : 'destructive'}>
          {turn.score ?? 0}/100
        </Badge>
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
