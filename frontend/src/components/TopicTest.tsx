import { useState } from 'react'

import {
  ApiError,
  fetchQuiz,
  gradeQuiz,
  type QuizRead,
  type QuizResultRead,
} from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { errorMessage } from '@/lib/errors'

const OPTION_LABELS = ['A', 'B', 'C', 'D']

/** Тест по теме: 10 вопросов с вариантами ответа и разбором после проверки. */
export function TopicTest({
  topicKey,
  token,
  onUnauthorized,
}: {
  topicKey: string
  token: string
  onUnauthorized?: () => void
}) {
  const [quiz, setQuiz] = useState<QuizRead | null>(null)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [result, setResult] = useState<QuizResultRead | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function start() {
    setBusy(true)
    setError(null)
    setResult(null)
    setAnswers({})
    try {
      setQuiz(await fetchQuiz(topicKey, token, 10))
    } catch (value) {
      if (value instanceof ApiError && value.status === 401) {
        onUnauthorized?.()
        return
      }
      setError(errorMessage(value))
    } finally {
      setBusy(false)
    }
  }

  async function grade() {
    if (quiz === null) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      const payload = quiz.questions.map((question) => ({
        question_id: question.id,
        selected_option: answers[question.id],
      }))
      setResult(await gradeQuiz(topicKey, payload, token))
      setQuiz(null)
    } catch (value) {
      if (value instanceof ApiError && value.status === 401) {
        onUnauthorized?.()
        return
      }
      setError(errorMessage(value))
    } finally {
      setBusy(false)
    }
  }

  if (result !== null) {
    return (
      <div className="flex flex-col gap-4 rounded-md border p-4">
        <div className="flex flex-wrap items-end gap-4">
          <span className="text-3xl font-medium">{result.level}</span>
          <span className="text-sm text-muted-foreground">
            {result.topic_name}: оценка знания темы
          </span>
          <Badge variant="outline">
            {result.correct_count} из {result.total} верно
          </Badge>
          <Badge variant="secondary">{Math.round(result.score * 100)}%</Badge>
        </div>
        <Progress value={result.level} />

        <ol className="flex list-decimal flex-col gap-4 pl-5 text-sm">
          {result.items.map((item) => (
            <li key={item.question_id} className="flex flex-col gap-1">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <span>{item.text}</span>
                {item.is_correct ? (
                  <Badge>верно</Badge>
                ) : (
                  <Badge variant="destructive">ошибка</Badge>
                )}
              </div>
              <span className="text-xs text-muted-foreground">
                Ваш ответ: {OPTION_LABELS[item.selected_option]}) {item.options[item.selected_option]}
              </span>
              {!item.is_correct ? (
                <span className="text-xs text-muted-foreground">
                  Правильно: {OPTION_LABELS[item.correct_option]}){' '}
                  {item.options[item.correct_option]}
                </span>
              ) : null}
              {item.explanation ? (
                <span className="text-xs text-muted-foreground">{item.explanation}</span>
              ) : null}
            </li>
          ))}
        </ol>

        <div>
          <Button type="button" variant="outline" onClick={() => void start()} disabled={busy}>
            {busy ? 'Готовим новый тест…' : 'Пройти ещё раз'}
          </Button>
        </div>
      </div>
    )
  }

  if (quiz !== null) {
    const answered = Object.keys(answers).length
    return (
      <div className="flex flex-col gap-4 rounded-md border p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm text-muted-foreground">
            {quiz.topic_name}: отвечено {answered} из {quiz.questions.length}
          </span>
          <Button type="button" size="sm" variant="ghost" onClick={() => setQuiz(null)}>
            Отменить
          </Button>
        </div>

        <ol className="flex flex-col gap-5">
          {quiz.questions.map((question, index) => (
            <li key={question.id} className="flex flex-col gap-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <span className="text-sm font-medium">
                  {index + 1}. {question.text}
                </span>
                <Badge variant="outline">сложность {question.difficulty}/5</Badge>
              </div>
              <div className="flex flex-col gap-1">
                {question.options.map((option, optionIndex) => (
                  <label
                    key={option}
                    className="flex cursor-pointer items-start gap-2 rounded-md border p-2 text-sm hover:bg-muted/50"
                  >
                    <input
                      type="radio"
                      name={`quiz-${question.id}`}
                      checked={answers[question.id] === optionIndex}
                      onChange={() =>
                        setAnswers((current) => ({ ...current, [question.id]: optionIndex }))
                      }
                    />
                    <span>
                      <span className="font-medium">{OPTION_LABELS[optionIndex]})</span> {option}
                    </span>
                  </label>
                ))}
              </div>
            </li>
          ))}
        </ol>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div>
          <Button
            type="button"
            onClick={() => void grade()}
            disabled={busy || answered < quiz.questions.length}
          >
            {busy ? 'Проверяем…' : 'Проверить ответы'}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="secondary" onClick={() => void start()} disabled={busy}>
          {busy ? 'Готовим тест…' : 'Пройти тест (10 вопросов)'}
        </Button>
        <span className="text-xs text-muted-foreground">
          Вопросы разной сложности, без выбора сложности.
        </span>
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  )
}
