import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  activateResume,
  ApiError,
  clearResumes,
  deleteResume,
  fetchResume,
  listResumes,
  type ResumeRead,
  type ResumeSummary,
} from '@/api/client'
import { CollapsibleCard } from '@/components/CollapsibleCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { formatDate } from '@/lib/labels'

function resumeTitle(resume: ResumeSummary | ResumeRead): string {
  return resume.title?.trim() || 'Резюме без названия'
}

export function ResumeHistoryCard({
  token,
  onUnauthorized,
}: {
  token: string
  onUnauthorized: () => void
}) {
  const queryClient = useQueryClient()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const resumesQuery = useQuery({
    queryKey: ['resumes', token],
    queryFn: () => listResumes(token),
    retry: false,
  })

  const detailQuery = useQuery({
    queryKey: ['resume', expandedId, token],
    queryFn: () => fetchResume(expandedId as string, token),
    enabled: expandedId !== null,
    retry: false,
  })

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['resumes'] }),
      queryClient.invalidateQueries({ queryKey: ['profile'] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
      queryClient.invalidateQueries({ queryKey: ['vacancies'] }),
    ])
  }

  async function run(action: () => Promise<unknown>, key: string) {
    setError(null)
    setBusy(key)
    try {
      await action()
      await refresh()
    } catch (value) {
      if (value instanceof ApiError && value.status === 401) {
        onUnauthorized()
        return
      }
      setError(errorMessage(value))
    } finally {
      setBusy(null)
    }
  }

  const resumes = resumesQuery.data ?? []

  return (
    <CollapsibleCard
      title="Мои резюме"
      description="История загрузок. Профиль знаний строится по активному резюме."
      storageKey="profile-resumes"
    >
      <div className="flex flex-col gap-4">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {resumesQuery.isPending ? (
          <p className="text-sm text-muted-foreground">Загружаем историю…</p>
        ) : resumesQuery.isError ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-destructive">{errorMessage(resumesQuery.error)}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void resumesQuery.refetch()}
            >
              Повторить
            </Button>
          </div>
        ) : resumes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Резюме пока нет. Загрузите первое в карточке выше.
          </p>
        ) : (
          <>
            <div className="flex flex-col gap-3">
              {resumes.map((resume) => (
                <div key={resume.id} className="rounded-md border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{resumeTitle(resume)}</span>
                      {resume.is_active ? <Badge>активно</Badge> : null}
                      <span className="text-xs text-muted-foreground">
                        {formatDate(resume.created_at)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        навыков: {resume.skills_count}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setExpandedId(expandedId === resume.id ? null : resume.id)
                        }
                      >
                        {expandedId === resume.id ? 'Скрыть' : 'Посмотреть'}
                      </Button>
                      {resume.is_active ? null : (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy !== null}
                          onClick={() =>
                            void run(
                              () => activateResume(resume.id, token),
                              resume.id,
                            )
                          }
                        >
                          {busy === resume.id ? 'Переключаем…' : 'Сделать активным'}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busy !== null}
                        onClick={() => {
                          if (!window.confirm(`Удалить резюме «${resumeTitle(resume)}»?`)) {
                            return
                          }
                          void run(() => deleteResume(resume.id, token), resume.id)
                        }}
                      >
                        Удалить
                      </Button>
                    </div>
                  </div>

                  {expandedId === resume.id ? (
                    <ResumeDetails
                      data={detailQuery.data}
                      isPending={detailQuery.isPending}
                      error={detailQuery.error}
                    />
                  ) : null}
                </div>
              ))}
            </div>

            <div>
              <Button
                variant="outline"
                size="sm"
                disabled={busy !== null}
                onClick={() => {
                  if (
                    !window.confirm(
                      'Удалить все резюме и оценки из них? Ручные оценки и интервью сохранятся.',
                    )
                  ) {
                    return
                  }
                  void run(() => clearResumes(token), 'clear')
                }}
              >
                {busy === 'clear' ? 'Очищаем…' : 'Очистить историю резюме'}
              </Button>
            </div>
          </>
        )}
      </div>
    </CollapsibleCard>
  )
}

function ResumeDetails({
  data,
  isPending,
  error,
}: {
  data: ResumeRead | undefined
  isPending: boolean
  error: unknown
}) {
  if (isPending) {
    return <p className="mt-3 text-sm text-muted-foreground">Загружаем резюме…</p>
  }
  if (error) {
    return <p className="mt-3 text-sm text-destructive">{errorMessage(error)}</p>
  }
  if (!data) {
    return null
  }
  return (
    <div className="mt-3 flex flex-col gap-3">
      <div className="max-h-64 overflow-auto rounded-md border bg-muted/40 p-3">
        <pre className="whitespace-pre-wrap font-sans text-sm">{data.raw_text}</pre>
      </div>
      <div className="flex flex-col gap-1 text-sm">
        {data.skills.length === 0 ? (
          <span className="text-muted-foreground">Навыки не найдены.</span>
        ) : (
          data.skills.map((skill) => (
            <div key={skill.id} className="flex justify-between gap-3">
              <span>{skill.raw_name}</span>
              <span className="text-muted-foreground">{skill.level}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
