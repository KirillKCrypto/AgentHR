import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  answerAssessment,
  ApiError,
  fetchAssessmentTopics,
  finishAssessment,
  startAssessment,
  type AssessmentFinishRead,
  type AssessmentStartRead,
} from '@/api/client'
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
import { errorMessage } from '@/lib/errors'

export function SkillAssessmentCard({
  token,
  topicKeys,
  onUnauthorized,
  onCompleted,
}: {
  token: string
  topicKeys: string[]
  onUnauthorized: () => void
  onCompleted: () => void
}) {
  const queryClient = useQueryClient()
  const [activeTopic, setActiveTopic] = useState<string | null>(null)
  const [attempt, setAttempt] = useState<AssessmentStartRead | null>(null)
  const [index, setIndex] = useState(0)
  const [result, setResult] = useState<AssessmentFinishRead | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const topicsQuery = useQuery({
    queryKey: ['assessment-topics', token],
    queryFn: () => fetchAssessmentTopics(token),
    retry: false,
  })

  const handleError = (value: unknown) => {
    if (value instanceof ApiError && value.status === 401) {
      onUnauthorized()
      return
    }
    setError(value)
  }

  const start = async (topicKey: string) => {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const data = await startAssessment(topicKey, token)
      setActiveTopic(topicKey)
      setAttempt(data)
      setIndex(0)
    } catch (value) {
      handleError(value)
    } finally {
      setBusy(false)
    }
  }

  const choose = async (answerKey: string) => {
    if (!attempt) {
      return
    }
    const question = attempt.questions[index]
    setBusy(true)
    setError(null)
    try {
      await answerAssessment(attempt.attempt_id, question.id, answerKey, token)
      if (index + 1 < attempt.questions.length) {
        setIndex(index + 1)
      } else {
        const finished = await finishAssessment(attempt.attempt_id, token)
        setResult(finished)
        setAttempt(null)
        setActiveTopic(null)
        void queryClient.invalidateQueries({ queryKey: ['assessment-topics', token] })
        onCompleted()
      }
    } catch (value) {
      handleError(value)
    } finally {
      setBusy(false)
    }
  }

  const reset = () => {
    setResult(null)
    setAttempt(null)
    setActiveTopic(null)
    setIndex(0)
    setError(null)
  }

  if (topicsQuery.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Проверка навыков</CardTitle>
          <CardDescription>Загружаем доступные тесты…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (topicsQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Проверка навыков</CardTitle>
          <CardDescription>{errorMessage(topicsQuery.error)}</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const allTopics = topicsQuery.data ?? []
  const topics = allTopics.filter((topic) => topicKeys.includes(topic.topic_key))

  return (
    <Card id="skill-assessment">
      <CardHeader>
        <CardTitle>Проверка навыков из резюме</CardTitle>
        <CardDescription>
          Выберите навык из профиля и пройдите тест: 10 вопросов, без таймера, с разбором.
          Каждый тест проходится один раз; результат подтверждает уровень.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error ? <p className="text-sm text-destructive">{errorMessage(error)}</p> : null}

        {result ? (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-end gap-4">
              <span className="text-3xl font-medium">{result.test_level}</span>
              <span className="text-sm text-muted-foreground">
                {result.topic_name ?? result.topic_key}: подтверждённый уровень
              </span>
              <Badge variant="outline">
                {result.correct_count} из {result.total} верно
              </Badge>
              <Badge variant="secondary">
                уверенность {Math.round(result.confidence * 100)}%
              </Badge>
            </div>
            <Progress value={result.test_level} />
            <div className="flex flex-col gap-3">
              {result.items.map((item) => (
                <div key={item.question_id} className="rounded-md border p-3 text-sm">
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-medium">{item.prompt}</span>
                    <Badge variant={item.is_correct ? 'default' : 'destructive'}>
                      {item.is_correct ? 'верно' : 'ошибка'}
                    </Badge>
                  </div>
                  {item.is_correct ? null : (
                    <p className="mt-2 text-muted-foreground">
                      Правильный ответ: {item.correct_key}. {item.explanation}
                    </p>
                  )}
                </div>
              ))}
            </div>
            <div>
              <Button variant="outline" onClick={reset}>
                Пройти другой тест
              </Button>
            </div>
          </div>
        ) : attempt ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-muted-foreground">
                {attempt.topic_name}: вопрос {index + 1} из {attempt.questions.length}
              </span>
              <Badge variant="outline">сложность {attempt.questions[index].difficulty}</Badge>
            </div>
            <Progress value={((index + 1) / attempt.questions.length) * 100} />
            <p className="text-lg font-medium">{attempt.questions[index].prompt}</p>
            <div className="flex flex-col gap-2">
              {attempt.questions[index].options.map((option) => (
                <Button
                  key={option.key}
                  variant="outline"
                  className="h-auto justify-start whitespace-normal py-3 text-left"
                  disabled={busy}
                  onClick={() => void choose(option.key)}
                >
                  {option.key}. {option.text}
                </Button>
              ))}
            </div>
            <div>
              <Button variant="ghost" size="sm" disabled={busy} onClick={reset}>
                Прервать
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {topics.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {topicKeys.length === 0
                  ? 'Сначала загрузите резюме — тесты появятся для извлечённых навыков.'
                  : 'Для извлечённых навыков тесты пока не настроены.'}
              </p>
            ) : (
              topics.map((topic) => (
                <div
                  key={topic.topic_key}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{topic.topic_name}</span>
                      {topic.completed ? <Badge>тест пройден</Badge> : null}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {topic.completed
                        ? `Подтверждённый уровень: ${topic.test_level ?? '—'}`
                        : `${topic.question_count} вопросов в банке`}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    disabled={busy || topic.completed || activeTopic === topic.topic_key}
                    onClick={() => void start(topic.topic_key)}
                  >
                    {topic.completed ? 'Пройден' : 'Проверить'}
                  </Button>
                </div>
              ))
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
