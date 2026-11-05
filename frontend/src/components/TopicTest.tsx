import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { fetchTestQuestions, type QuestionRead } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'

/** Тест по теме: 10 случайных вопросов разной сложности. */
export function TopicTest({ topicKey, token }: { topicKey: string; token: string }) {
  const [open, setOpen] = useState(false)
  const questionsQuery = useQuery<QuestionRead[]>({
    queryKey: ['questions', topicKey, token],
    queryFn: () => fetchTestQuestions(topicKey, token, 10),
    enabled: open,
    retry: false,
  })

  return (
    <div className="flex flex-col gap-2 rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant={open ? 'outline' : 'secondary'}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? 'Скрыть тест' : 'Пройти тест (10 вопросов)'}
        </Button>
        {open ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => void questionsQuery.refetch()}
            disabled={questionsQuery.isFetching}
          >
            Другой набор
          </Button>
        ) : null}
      </div>

      {open ? (
        questionsQuery.isPending ? (
          <p className="text-sm text-muted-foreground">Загружаем вопросы…</p>
        ) : questionsQuery.isError ? (
          <p className="text-sm text-destructive">{errorMessage(questionsQuery.error)}</p>
        ) : (questionsQuery.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Вопросов по теме пока нет — банк ещё наполняется.
          </p>
        ) : (
          <ol className="flex list-decimal flex-col gap-3 pl-5 text-sm">
            {(questionsQuery.data ?? []).map((question) => (
              <li key={question.id} className="flex flex-col gap-1">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <span>{question.text}</span>
                  <Badge variant="outline">сложность {question.difficulty}/5</Badge>
                </div>
                {question.expected_points.length > 0 ? (
                  <details>
                    <summary className="cursor-pointer text-xs text-muted-foreground">
                      Эталонные пункты ответа
                    </summary>
                    <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
                      {question.expected_points.map((point) => (
                        <li key={point}>{point}</li>
                      ))}
                    </ul>
                  </details>
                ) : null}
              </li>
            ))}
          </ol>
        )
      ) : null}
    </div>
  )
}
