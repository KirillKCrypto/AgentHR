import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import {
  ApiError,
  answerInterview,
  fetchInterview,
  streamInterviewAnswer,
  type InterviewRead,
  type InterviewTurnRead,
} from '@/api/client'
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

  const currentTurn = session?.turns.find((turn) => turn.status === 'pending') ?? null
  const completed = session?.status === 'completed'

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
  const progress = session.question_count
    ? Math.round((answered.length / session.question_count) * 100)
    : 0

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{session.title || 'Тренировочное интервью'}</CardTitle>
          <CardDescription>
            Отвечено {answered.length} из {session.question_count}. Интервью можно проходить
            повторно.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Progress value={completed ? 100 : progress} />
          {completed ? (
            <div className="flex flex-wrap items-end gap-4">
              <span className="text-3xl font-medium">{session.level ?? 0}</span>
              <span className="text-sm text-muted-foreground">итоговый уровень</span>
              <Badge variant="outline">
                {Math.round((session.score ?? 0) * 100)}% по сложности
              </Badge>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {answered.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Разбор предыдущих ответов</CardTitle>
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
            <CardTitle>Интервью завершено</CardTitle>
            <CardDescription>
              Результат сохранён в профиле. Слабые темы подсвечены в разборе.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Link to="/profile" className={buttonVariants()}>
              Открыть профиль
            </Link>
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
            </CardTitle>
            <CardDescription>
              Сложность {currentTurn.difficulty}/5. Ответьте текстом, интервьюер оценит
              полноту.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
              <p className="text-sm">{currentTurn.question_text}</p>
              <Textarea
                rows={6}
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                placeholder="Ваш ответ: определения, примеры, trade-offs."
              />
              {streamedFeedback ? (
                <div className="rounded-md border bg-muted/40 p-3 text-sm">
                  {streamedFeedback}
                  {busy ? <span className="animate-pulse">▍</span> : null}
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

function AnsweredTurn({ turn }: { turn: InterviewTurnRead }) {
  return (
    <div className="flex flex-col gap-1 border-b pb-3 last:border-b-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">
          {turn.position}. {turn.topic_name}
        </span>
        <Badge variant={(turn.score ?? 0) >= 70 ? 'default' : 'destructive'}>
          {turn.score ?? 0}/100
        </Badge>
      </div>
      <span className="text-xs text-muted-foreground">{turn.question_text}</span>
      {turn.feedback ? <span className="text-sm">{turn.feedback}</span> : null}
      {turn.missed_points.length > 0 ? (
        <span className="text-xs text-muted-foreground">
          Упущено: {turn.missed_points.join('; ')}
        </span>
      ) : null}
    </div>
  )
}
