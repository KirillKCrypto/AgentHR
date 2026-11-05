import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import {
  ApiError,
  fetchGaps,
  fetchProfile,
  listVacancies,
  type GapAnalysisRead,
  type ProfileRead,
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
import { CreatePlanButton } from '@/components/CreatePlanButton'
import { GapMetrics, GapRecommendations, GapTable } from '@/components/Gaps'
import { ResumeUploadCard } from '@/components/ResumeUploadCard'
import { SkillAssessmentCard } from '@/components/SkillAssessmentCard'
import { errorMessage } from '@/lib/errors'
import { formatDate, sourceLabel } from '@/lib/labels'
import { useAuthToken } from '@/lib/useAuthToken'

type ProfileTopic = ProfileRead['topics'][number]
type GapItem = GapAnalysisRead['items'][number]

export default function ProfilePage() {
  const { token, expire } = useAuthToken()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const [selectedVacancyId, setSelectedVacancyId] = useState<string | null>(() =>
    searchParams.get('vacancy'),
  )

  const profileQuery = useQuery({
    queryKey: ['profile', token],
    queryFn: () => fetchProfile(token as string),
    enabled: token !== null,
    retry: false,
  })

  const vacanciesQuery = useQuery({
    queryKey: ['vacancies', token],
    queryFn: () => listVacancies(token as string),
    enabled: token !== null,
    retry: false,
  })

  useEffect(() => {
    const vacancies = vacanciesQuery.data
    if (!vacancies) {
      return
    }
    if (vacancies.length === 0) {
      setSelectedVacancyId(null)
      return
    }
    if (selectedVacancyId && vacancies.some((item) => item.id === selectedVacancyId)) {
      return
    }
    setSelectedVacancyId(vacancies[0].id)
  }, [vacanciesQuery.data, selectedVacancyId])

  const gapsQuery = useQuery({
    queryKey: ['gaps', selectedVacancyId, token],
    queryFn: () => fetchGaps(selectedVacancyId as string, token as string),
    enabled: token !== null && selectedVacancyId !== null,
    retry: false,
  })

  const queryError = profileQuery.error ?? vacanciesQuery.error ?? gapsQuery.error
  useEffect(() => {
    if (queryError instanceof ApiError && queryError.status === 401) {
      expire()
    }
  }, [queryError, expire])

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Профиль знаний</CardTitle>
          <CardDescription>Войдите, чтобы увидеть свой профиль и разрывы.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (profileQuery.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Профиль знаний</CardTitle>
          <CardDescription>Загружаем профиль…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Профиль знаний</CardTitle>
          <CardDescription>{errorMessage(profileQuery.error)}</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Button variant="outline" onClick={() => void profileQuery.refetch()}>
            Повторить
          </Button>
          <Link to="/vacancies/new" className={buttonVariants()}>
            Новая подготовка
          </Link>
        </CardContent>
      </Card>
    )
  }

  const profile = profileQuery.data
  const gaps = gapsQuery.data
  const gapByTopic = new Map<string, GapItem>()
  for (const item of gaps?.items ?? []) {
    if (item.topic_key) {
      gapByTopic.set(item.topic_key, item)
    }
  }

  const canonicalTopics = profile.topics.filter((topic) => topic.status !== 'provisional')
  const provisionalTopics = profile.topics.filter((topic) => topic.status === 'provisional')
  const isEmpty = profile.topics.length === 0 && profile.unmatched_skills.length === 0

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Профиль знаний</CardTitle>
          <CardDescription>
            Сначала загрузите резюме — AgentHR извлечёт навыки и оценит уровень по каждой
            теме от 0 до 100. Затем проверьте вакансию: профиль переиспользуется.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Link to="/vacancies/new" className={buttonVariants()}>
            Проверить вакансию
          </Link>
          {isEmpty ? null : <CreatePlanButton label="Построить план по профилю" />}
          <Button
            variant="outline"
            onClick={() => {
              void profileQuery.refetch()
              void vacanciesQuery.refetch()
            }}
          >
            Обновить
          </Button>
        </CardContent>
      </Card>

      <ResumeUploadCard token={token} onUnauthorized={expire} />

      <SkillAssessmentCard
        token={token}
        topicKeys={profile.topics.map((topic) => topic.topic_key)}
        onUnauthorized={expire}
        onCompleted={() => {
          void queryClient.invalidateQueries({ queryKey: ['profile', token] })
          void queryClient.invalidateQueries({ queryKey: ['gaps'] })
        }}
      />

      {isEmpty ? (
        <Card>
          <CardHeader>
            <CardTitle>Профиль пока пуст</CardTitle>
            <CardDescription>
              Загрузите резюме в карточке выше. Навыки, темы и оценки появятся здесь.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Темы</CardTitle>
              <CardDescription>
                Подтверждённые темы: владение 0–100, источник и уверенность под шкалой.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              {canonicalTopics.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Подтверждённых тем пока нет — загрузите резюме.
                </p>
              ) : (
                canonicalTopics.map((topic) => (
                  <TopicRow
                    key={topic.topic_id}
                    topic={topic}
                    gap={gapByTopic.get(topic.topic_key)}
                  />
                ))
              )}
            </CardContent>
          </Card>

          {provisionalTopics.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Непроверенные темы</CardTitle>
                <CardDescription>
                  Созданы автоматически из новых навыков. Учитываются в покрытии, но не в
                  подтверждённой готовности до ревью.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-5">
                {provisionalTopics.map((topic) => (
                  <TopicRow
                    key={topic.topic_id}
                    topic={topic}
                    gap={gapByTopic.get(topic.topic_key)}
                  />
                ))}
              </CardContent>
            </Card>
          ) : null}

          <GapsSection
            profile={profile}
            gaps={gaps}
            isPending={gapsQuery.isPending}
            error={gapsQuery.error}
            vacanciesPending={vacanciesQuery.isPending}
            vacanciesError={vacanciesQuery.error}
            vacancies={vacanciesQuery.data ?? []}
            selectedVacancyId={selectedVacancyId}
            onSelect={setSelectedVacancyId}
            onRetry={() => void gapsQuery.refetch()}
          />

          <Card>
            <CardHeader>
              <CardTitle>Навыки вне онтологии</CardTitle>
              <CardDescription>
                Сохранены из резюме как есть; в готовность к вакансии не входят.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {profile.unmatched_skills.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Все навыки из резюме сопоставлены с темами.
                </p>
              ) : (
                <div className="flex flex-col gap-2">
                  {profile.unmatched_skills.map((skill) => (
                    <div
                      key={`${skill.raw_name}-${skill.level}`}
                      className="flex items-center justify-between gap-3 text-sm"
                    >
                      <span>{skill.raw_name}</span>
                      <span className="text-muted-foreground">уровень {skill.level}</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

function TopicRow({ topic, gap }: { topic: ProfileTopic; gap?: GapItem }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{topic.topic_name}</span>
          {topic.status === 'provisional' ? (
            <Badge variant="secondary">на проверке</Badge>
          ) : null}
          {topic.category ? <Badge variant="outline">{topic.category}</Badge> : null}
          {topic.verified_level !== null ? (
            <Badge>подтверждено тестом</Badge>
          ) : (
            <Badge variant="outline">самоотчёт</Badge>
          )}
          {gap && !gap.satisfied ? (
            <Badge variant="destructive">пробел −{gap.gap}</Badge>
          ) : null}
        </div>
        <span className="text-sm tabular-nums">{topic.proficiency}%</span>
      </div>
      <Progress value={topic.proficiency} />
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <span>источник: {sourceLabel(topic.source)}</span>
        {topic.claimed_level !== null ? (
          <>
            <span>·</span>
            <span>в резюме: {topic.claimed_level}%</span>
          </>
        ) : null}
        {topic.verified_level !== null ? (
          <>
            <span>·</span>
            <span>тест: {topic.verified_level}%</span>
          </>
        ) : null}
        <span>·</span>
        <span>уверенность: {Math.round(topic.confidence * 100)}%</span>
        {topic.last_assessed ? (
          <>
            <span>·</span>
            <span>{formatDate(topic.last_assessed)}</span>
          </>
        ) : null}
      </div>
    </div>
  )
}

function GapsSection({
  profile,
  gaps,
  isPending,
  error,
  vacanciesPending,
  vacanciesError,
  vacancies,
  selectedVacancyId,
  onSelect,
  onRetry,
}: {
  profile: ProfileRead
  gaps: GapAnalysisRead | undefined
  isPending: boolean
  error: unknown
  vacanciesPending: boolean
  vacanciesError: unknown
  vacancies: { id: string; title?: string | null; company?: string | null }[]
  selectedVacancyId: string | null
  onSelect: (id: string) => void
  onRetry: () => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Разрывы по вакансии</CardTitle>
        <CardDescription>
          Выберите вакансию — темы с пробелами подсветятся выше.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {vacanciesPending ? (
          <p className="text-sm text-muted-foreground">Загружаем вакансии…</p>
        ) : vacanciesError ? (
          <p className="text-sm text-destructive">{errorMessage(vacanciesError)}</p>
        ) : vacancies.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Вакансий пока нет.{' '}
            <Link to="/vacancies/new" className="underline underline-offset-4">
              Загрузите первую
            </Link>
            .
          </p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {vacancies.map((vacancy) => (
                <Button
                  key={vacancy.id}
                  size="sm"
                  variant={vacancy.id === selectedVacancyId ? 'default' : 'outline'}
                  onClick={() => onSelect(vacancy.id)}
                >
                  {vacancy.title ?? 'Без названия'}
                  {vacancy.company ? ` · ${vacancy.company}` : ''}
                </Button>
              ))}
            </div>

            {selectedVacancyId ? (
              <Link
                to={`/vacancies/${selectedVacancyId}`}
                className="text-sm underline underline-offset-4"
              >
                Открыть текст вакансии
              </Link>
            ) : null}

            {isPending ? (
              <p className="text-sm text-muted-foreground">Считаем разрывы…</p>
            ) : error ? (
              <div className="flex flex-col gap-2">
                <p className="text-sm text-destructive">{errorMessage(error)}</p>
                <div>
                  <Button variant="outline" size="sm" onClick={onRetry}>
                    Повторить
                  </Button>
                </div>
              </div>
            ) : gaps ? (
              <GapsView gaps={gaps} hasTopics={profile.topics.length > 0} />
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  )
}

function GapsView({ gaps, hasTopics }: { gaps: GapAnalysisRead; hasTopics: boolean }) {
  return (
    <div className="flex flex-col gap-3">
      {hasTopics ? (
        <GapMetrics gaps={gaps} />
      ) : (
        <p className="text-sm text-muted-foreground">
          Профиль пуст — все требования пока считаются разрывами.
        </p>
      )}
      <GapTable items={gaps.items} />
      <GapRecommendations items={gaps.recommendations} />
    </div>
  )
}
