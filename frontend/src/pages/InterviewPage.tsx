import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import {
  ApiError,
  answerInterview,
  fetchInterview,
  fetchInterviewReport,
  streamInterviewAnswer,
  transcribeAudio,
  type InterviewRead,
  type InterviewReportRead,
  type InterviewReportTopicRead,
  type InterviewTurnRead,
} from '@/api/client'
import { AudioWaveform } from '@/components/AudioWaveform'
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
  const [streamedTurnId, setStreamedTurnId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [inputMode, setInputMode] = useState<'text' | 'voice'>('text')
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null)
  const [clock, setClock] = useState(() => Date.now())
  const [serverOffset, setServerOffset] = useState(0)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const pendingTimeoutRef = useRef(false)
  const timeoutSentRef = useRef<string | null>(null)

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
    setStreamedTurnId(null)
    setError(null)
  }, [interviewId])

  const currentTurn = session?.turns.find((turn) => turn.status === 'pending') ?? null
  const draftKey =
    session && currentTurn
      ? `interview-draft:${session.id}:${currentTurn.id}`
      : null

  useEffect(() => {
    if (!draftKey) {
      return
    }
    setAnswer(window.localStorage.getItem(draftKey) ?? '')
  }, [draftKey])

  useEffect(() => {
    if (session?.server_time) {
      setServerOffset(new Date(session.server_time).getTime() - Date.now())
    }
  }, [session?.server_time])

  useEffect(() => {
    if (completed) {
      return
    }
    const timer = window.setInterval(() => setClock(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [completed])

  const deadline = currentTurn?.deadline_at
    ? new Date(currentTurn.deadline_at).getTime()
    : null
  const remaining =
    deadline === null
      ? null
      : Math.max(0, Math.floor((deadline - (clock + serverOffset)) / 1000))

  useEffect(() => {
    if (!currentTurn || remaining === null || remaining > 0) {
      return
    }
    if (recording) {
      pendingTimeoutRef.current = true
      stopRecording()
      return
    }
    if (busy || transcribing) {
      return
    }
    if (timeoutSentRef.current === currentTurn.id) {
      return
    }
    timeoutSentRef.current = currentTurn.id
    const text = answer.trim()
    if (text.length >= 3) {
      void submitAnswer(text, inputMode, false)
    } else {
      void submitAnswer('', inputMode, true)
    }
  }, [remaining, currentTurn, busy, recording, transcribing])

  async function submitAnswer(
    text: string,
    mode: 'text' | 'voice',
    timedOut: boolean,
  ) {
    if (token === null || session === null || currentTurn === null) {
      return
    }
    const sessionId = session.id
    const turnId = currentTurn.id
    const key = draftKey
    setBusy(true)
    setError(null)
    setStreamedFeedback('')

    if (timedOut) {
      try {
        const result = await answerInterview(
          sessionId,
          turnId,
          '',
          token,
          mode,
          true,
        )
        setSession(result.session)
        setAnswer('')
        if (key) {
          window.localStorage.removeItem(key)
        }
      } catch (value) {
        if (value instanceof ApiError && value.status === 401) {
          expire()
          return
        }
        setError(errorMessage(value))
      } finally {
        setBusy(false)
      }
      return
    }

    let evaluated = false
    try {
      await streamInterviewAnswer(
        sessionId,
        turnId,
        text,
        token,
        (name, data) => {
          if (name === 'evaluation') {
            evaluated = true
            const updated = data.session as InterviewRead | undefined
            if (updated) {
              setSession(updated)
              setAnswer('')
              if (key) {
                window.localStorage.removeItem(key)
              }
            }
            setStreamedFeedback('')
            setStreamedTurnId(
              typeof data.turn === 'object' && data.turn !== null && 'id' in data.turn
                ? String(data.turn.id)
                : null,
            )
          } else if (name === 'token') {
            const chunk = typeof data.text === 'string' ? data.text : ''
            setStreamedFeedback((current) => current + chunk)
          } else if (name === 'done') {
            const updated = data.session as InterviewRead
            setSession(updated)
            setAnswer('')
            if (key) {
              window.localStorage.removeItem(key)
            }
            setStreamedFeedback('')
            setStreamedTurnId(null)
          }
        },
        undefined,
        mode,
      )
    } catch (value) {
      if (value instanceof ApiError && value.status === 401) {
        expire()
        return
      }
      if (!evaluated) {
        try {
          const fallback = await answerInterview(
            sessionId,
            turnId,
            text,
            token,
            mode,
          )
          setSession(fallback.session)
          setStreamedFeedback(fallback.turn.feedback ?? '')
          setStreamedTurnId(fallback.turn.id)
          setAnswer('')
          if (key) {
            window.localStorage.removeItem(key)
          }
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (recording) {
      setError('Остановите запись перед отправкой.')
      return
    }
    const text = answer.trim()
    if (text.length < 3) {
      setError('Напишите ответ подробнее.')
      return
    }
    await submitAnswer(text, inputMode, false)
  }

  async function startRecording() {
    if (token === null || session === null || currentTurn === null) {
      return
    }
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data)
        }
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        setMediaStream(null)
        setRecording(false)
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || 'audio/webm',
        })
        void finishRecording(
          blob,
          session.id,
          currentTurn.id,
          draftKey,
        )
      }
      recorderRef.current = recorder
      setMediaStream(stream)
      setRecording(true)
      recorder.start()
    } catch {
      setError('Не удалось получить доступ к микрофону.')
    }
  }

  function stopRecording() {
    recorderRef.current?.stop()
    recorderRef.current = null
  }

  async function finishRecording(
    blob: Blob,
    sessionId: string,
    turnId: string,
    key: string | null,
  ) {
    if (blob.size === 0 || token === null) {
      return
    }
    setTranscribing(true)
    try {
      const result = await transcribeAudio(sessionId, turnId, blob, token)
      const addition = result.text.trim()
      const combined = [answer.trim(), addition].filter(Boolean).join(' ')
      setAnswer(combined)
      if (key) {
        window.localStorage.setItem(key, combined)
      }
      if (pendingTimeoutRef.current) {
        pendingTimeoutRef.current = false
        await submitAnswer(combined, 'voice', combined.length < 3)
      }
    } catch (value) {
      if (value instanceof ApiError && value.status === 401) {
        expire()
        return
      }
      setError(errorMessage(value))
    } finally {
      setTranscribing(false)
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
              <AnsweredTurn
                key={turn.id}
                turn={turn}
                streamingFeedback={
                  turn.id === streamedTurnId ? streamedFeedback : null
                }
              />
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
              Сложность {currentTurn.difficulty}/5. Ответьте текстом или голосом —
              интервьюер оценит полноту.
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
              <div className="flex flex-wrap items-center justify-between gap-2">
                {remaining !== null ? (
                  <Badge
                    variant={
                      remaining <= 30
                        ? 'destructive'
                        : remaining <= 60
                          ? 'secondary'
                          : 'outline'
                    }
                  >
                    Осталось {formatSeconds(remaining)}
                  </Badge>
                ) : (
                  <span />
                )}
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={inputMode === 'text' ? 'default' : 'outline'}
                    disabled={recording || transcribing}
                    onClick={() => setInputMode('text')}
                  >
                    Текст
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={inputMode === 'voice' ? 'default' : 'outline'}
                    disabled={recording || transcribing}
                    onClick={() => setInputMode('voice')}
                  >
                    Голос
                  </Button>
                </div>
              </div>
              {inputMode === 'voice' ? (
                <div className="flex flex-col gap-2 rounded-md border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant={recording ? 'destructive' : 'secondary'}
                      disabled={transcribing || busy}
                      onClick={() => {
                        if (recording) {
                          stopRecording()
                        } else {
                          void startRecording()
                        }
                      }}
                    >
                      {recording
                        ? 'Остановить запись'
                        : transcribing
                          ? 'Распознаём…'
                          : 'Начать запись'}
                    </Button>
                    <span className="text-xs text-muted-foreground">
                      {recording
                        ? 'Идёт запись ответа'
                        : transcribing
                          ? 'Расшифровываем аудио'
                          : 'Аудио не сохраняется'}
                    </span>
                  </div>
                  {recording ? <AudioWaveform stream={mediaStream} active /> : null}
                </div>
              ) : null}
              <div className="flex flex-col gap-1">
                <p className="text-sm font-medium">Ответ</p>
                <Textarea
                  rows={6}
                  value={answer}
                  onChange={(event) => {
                    setAnswer(event.target.value)
                    if (draftKey) {
                      window.localStorage.setItem(draftKey, event.target.value)
                    }
                  }}
                  placeholder="Определения, примеры, trade-offs."
                />
              </div>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <div>
                <Button
                  type="submit"
                  disabled={busy || recording || transcribing}
                >
                  {busy
                    ? streamedTurnId
                      ? 'Готовим анализ…'
                      : 'Интервьюер оценивает…'
                    : 'Ответить'}
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

function formatSeconds(total: number): string {
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function AnsweredTurn({
  turn,
  streamingFeedback = null,
}: {
  turn: InterviewTurnRead
  streamingFeedback?: string | null
}) {
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
        <span className="text-sm">
          {streamingFeedback !== null ? (
            <>
              {streamingFeedback}
              <span className="animate-pulse">▍</span>
            </>
          ) : (
            turn.feedback ?? '—'
          )}
        </span>
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
