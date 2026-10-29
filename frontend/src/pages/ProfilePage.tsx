import { useQuery } from '@tanstack/react-query'
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage } from '@/lib/errors'
import { formatDate, sourceLabel } from '@/lib/labels'
import { useAuthToken } from '@/lib/useAuthToken'

type ProfileTopic = ProfileRead['topics'][number]
type GapItem = GapAnalysisRead['items'][number]

export default function ProfilePage() {
  const { token, expire } = useAuthToken()
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
            Оценки по темам онтологии и навыки вне словаря. Профиль обновляется
            при загрузке резюме и переиспользуется между вакансиями.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Link to="/vacancies/new" className={buttonVariants()}>
            Новая подготовка
          </Link>
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

      {isEmpty ? (
        <Card>
          <CardHeader>
            <CardTitle>Профиль пока пуст</CardTitle>
            <CardDescription>
              Загрузите вакансию и резюме — темы и пробелы появятся здесь.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link to="/vacancies/new" className={buttonVariants()}>
              Загрузить вакансию и резюме
            </Link>
          </CardContent>
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
          {gap && !gap.satisfied ? (
            <Badge variant="destructive">пробел −{gap.gap}</Badge>
          ) : null}
        </div>
        <span className="text-sm tabular-nums">{topic.proficiency}%</span>
      </div>
      <Progress value={topic.proficiency} />
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <span>источник: {sourceLabel(topic.source)}</span>
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
  const coverage = Math.round(gaps.coverage_all * 100)
  const confirmed =
    gaps.confirmed_readiness === null || gaps.confirmed_readiness === undefined
      ? null
      : Math.round(gaps.confirmed_readiness * 100)

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <span className="text-2xl font-medium">{coverage}%</span>
          <span className="text-sm text-muted-foreground">покрытие всех требований</span>
          <Progress value={coverage} />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-2xl font-medium">
            {confirmed === null ? '—' : `${confirmed}%`}
          </span>
          <span className="text-sm text-muted-foreground">подтверждённая готовность</span>
          {confirmed === null ? (
            <span className="text-xs text-muted-foreground">
              нет подтверждённых требований
            </span>
          ) : (
            <Progress value={confirmed} />
          )}
        </div>
      </div>
      <div className="flex items-end justify-between gap-3">
        <span className="text-sm text-muted-foreground">
          {gaps.items.filter((item) => item.satisfied).length} из {gaps.items.length}{' '}
          требований закрыто
        </span>
      </div>
      {hasTopics ? null : (
        <p className="text-sm text-muted-foreground">
          Профиль пуст — все требования пока считаются разрывами.
        </p>
      )}
      {gaps.provisional_count > 0 ? (
        <p className="text-sm text-muted-foreground">
          {gaps.provisional_count} требований опираются на непроверенные темы (вес{' '}
          {gaps.provisional_weight.toFixed(2)}). Они входят в покрытие, но не в
          подтверждённую готовность.
        </p>
      ) : null}
      {gaps.critical_gap_count > 0 ? (
        <p className="text-sm text-destructive">
          {gaps.critical_gap_count} обязательных требований не закрыто.
        </p>
      ) : null}
      {gaps.unmatched_count > 0 ? (
        <p className="text-sm text-muted-foreground">
          {gaps.unmatched_count} навык(ов) вакансии вне онтологии: показаны в таблице,
          но не входят в покрытие.
        </p>
      ) : null}
      {gaps.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Требований в вакансии нет.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Навык</TableHead>
              <TableHead>Тема</TableHead>
              <TableHead>Требуется</TableHead>
              <TableHead>В профиле</TableHead>
              <TableHead>Разрыв</TableHead>
              <TableHead>Критичность</TableHead>
              <TableHead>Логика</TableHead>
              <TableHead>Статус</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {gaps.items.map((item) => (
              <TableRow key={item.skill_name}>
                <TableCell>{item.skill_name}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap items-center gap-2">
                    {item.topic_name ?? <Badge variant="outline">вне онтологии</Badge>}
                    {item.topic_status === 'provisional' ? (
                      <Badge variant="secondary">на проверке</Badge>
                    ) : null}
                  </div>
                </TableCell>
                <TableCell>{item.required_level}</TableCell>
                <TableCell>{item.user_level}</TableCell>
                <TableCell>{item.gap}</TableCell>
                <TableCell>
                  {item.criticality === 'must_have' ? (
                    <Badge>обязательно</Badge>
                  ) : (
                    <Badge variant="outline">желательно</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {item.requirement_logic === 'SINGLE' ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <Badge variant="outline">{item.requirement_logic}</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {item.satisfied ? (
                    <Badge>закрыто</Badge>
                  ) : (
                    <Badge variant="destructive">разрыв</Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
