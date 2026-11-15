import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import {
  ApiError,
  fetchDashboard,
  fetchMe,
  listVacancies,
  type DashboardRead,
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
import { errorMessage } from '@/lib/errors'
import { formatDate } from '@/lib/labels'
import { clearTokens, getAccessToken } from '@/lib/tokens'

export default function DashboardPage() {
  const navigate = useNavigate()
  const [token, setToken] = useState<string | null>(() => getAccessToken())
  const [vacancyId, setVacancyId] = useState<string | null>(null)

  const meQuery = useQuery({
    queryKey: ['me', token],
    queryFn: () => fetchMe(token as string),
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
    if (!vacancies || vacancies.length === 0) {
      setVacancyId(null)
      return
    }
    if (vacancyId && vacancies.some((item) => item.id === vacancyId)) {
      return
    }
    setVacancyId(vacancies[0].id)
  }, [vacanciesQuery.data, vacancyId])

  const dashboardQuery = useQuery<DashboardRead>({
    queryKey: ['dashboard', vacancyId, token],
    queryFn: () => fetchDashboard(token as string, vacancyId),
    enabled: token !== null,
    retry: false,
  })

  useEffect(() => {
    const error = meQuery.error ?? dashboardQuery.error
    if (error instanceof ApiError && error.status === 401) {
      clearTokens()
      setToken(null)
    }
  }, [meQuery.error, dashboardQuery.error])

  function handleLogout() {
    clearTokens()
    setToken(null)
  }

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Дашборд</CardTitle>
          <CardDescription>Войдите, чтобы увидеть прогресс подготовки.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => navigate('/login')}>Войти</Button>
        </CardContent>
      </Card>
    )
  }

  if (meQuery.isPending || dashboardQuery.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Дашборд</CardTitle>
          <CardDescription>Собираем прогресс…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (meQuery.isError || dashboardQuery.isError || !dashboardQuery.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Дашборд</CardTitle>
          <CardDescription>
            {errorMessage(dashboardQuery.error ?? meQuery.error)}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Button variant="outline" onClick={() => void dashboardQuery.refetch()}>
            Повторить
          </Button>
          <Button variant="ghost" onClick={handleLogout}>
            Выйти
          </Button>
        </CardContent>
      </Card>
    )
  }

  const data = dashboardQuery.data
  const vacancies = vacanciesQuery.data ?? []
  const hasProfile = data.profile.topics_count > 0
  const hasVacancy = data.vacancy !== null
  const lastInterview = data.last_interview

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Дашборд</CardTitle>
          <CardDescription>
            {meQuery.data ? `Вы вошли как ${meQuery.data.email}. ` : ''}
            {hasProfile
              ? 'Показываем готовность, последний результат и следующий шаг.'
              : 'Начните с резюме — построим профиль знаний и покажем пробелы.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          {!hasProfile ? (
            <Link to="/profile" className={buttonVariants()}>
              Загрузить резюме
            </Link>
          ) : !hasVacancy ? (
            <Link to="/vacancies/new" className={buttonVariants()}>
              Проверить вакансию
            </Link>
          ) : (
            <Link
              to={`/vacancies/${data.vacancy?.id}`}
              className={buttonVariants()}
            >
              {lastInterview ? 'Открыть вакансию' : 'Пройти интервью'}
            </Link>
          )}
          {lastInterview ? (
            <Link
              to={`/reports/${lastInterview.id}`}
              className={buttonVariants({ variant: 'outline' })}
            >
              Последний отчёт
            </Link>
          ) : null}
          {hasProfile ? (
            <Link to="/profile" className={buttonVariants({ variant: 'outline' })}>
              Профиль знаний
            </Link>
          ) : null}
          <Button variant="ghost" className="ml-auto" onClick={handleLogout}>
            Выйти
          </Button>
        </CardContent>
      </Card>

      {data.active_interview ? (
        <Card>
          <CardHeader>
            <CardTitle>Незавершённое интервью</CardTitle>
            <CardDescription>
              {data.active_interview.vacancy_title ?? 'Интервью по вакансии'} ·
              отвечено {data.active_interview.answered_count} из{' '}
              {data.active_interview.max_questions}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Progress
              value={Math.round(
                (data.active_interview.answered_count /
                  Math.max(1, data.active_interview.max_questions)) *
                  100,
              )}
            />
            <div>
              <Link
                to={`/interviews/${data.active_interview.id}`}
                className={buttonVariants()}
              >
                Продолжить интервью
              </Link>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Тем в профиле"
          value={data.profile.topics_count}
          hint={`${data.profile.confirmed_count} подтверждено`}
        />
        <StatCard
          label="Пройдено тестов"
          value={data.tests.completed_count}
          hint={
            data.tests.average_level === null ||
            data.tests.average_level === undefined
              ? 'Средний уровень пока не считается'
              : `Средний уровень ${Math.round(data.tests.average_level)}`
          }
        />
        <StatCard
          label="Активность"
          value={data.activity.interviews_completed}
          hint={`интервью · ${data.activity.tests_completed} тестов`}
        />
      </div>

      {data.vacancy ? (
        <ReadinessCard data={data} vacancies={vacancies} onSelect={setVacancyId} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Готовность к вакансии</CardTitle>
            <CardDescription>
              Загрузите вакансию — сравним требования с профилем и покажем, где
              не хватает уровня.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link to="/vacancies/new" className={buttonVariants()}>
              Загрузить вакансию
            </Link>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Последнее интервью</CardTitle>
            <CardDescription>
              {lastInterview?.vacancy_title ?? 'Интервью по вакансии'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {lastInterview ? (
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-end gap-3">
                  <span className="text-4xl font-medium">
                    {lastInterview.level ?? 0}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    итоговый уровень · {Math.round(lastInterview.score ?? 0)}/100
                  </span>
                  {typeof lastInterview.delta === 'number' ? (
                    <Badge variant={lastInterview.delta >= 0 ? 'default' : 'destructive'}>
                      {lastInterview.delta >= 0 ? '+' : ''}
                      {lastInterview.delta} к прошлому
                    </Badge>
                  ) : (
                    <Badge variant="outline">первое интервью</Badge>
                  )}
                </div>
                <span className="text-sm text-muted-foreground">
                  {lastInterview.finished_at
                    ? formatDate(lastInterview.finished_at)
                    : '—'}
                </span>
                <div className="flex flex-wrap gap-2">
                  <Link
                    to={`/reports/${lastInterview.id}`}
                    className={buttonVariants()}
                  >
                    Открыть отчёт
                  </Link>
                  {lastInterview.vacancy_id ? (
                    <Link
                      to={`/vacancies/${lastInterview.vacancy_id}`}
                      className={buttonVariants({ variant: 'outline' })}
                    >
                      К вакансии
                    </Link>
                  ) : null}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Интервью пока не пройдено. Откройте вакансию и запустите тренировку.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>План подготовки</CardTitle>
            <CardDescription>
              {data.plan ? data.plan.title : 'Плана пока нет'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.plan ? (
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-end justify-between gap-2">
                  <span className="text-3xl font-medium">
                    {Math.round(data.plan.progress * 100)}%
                  </span>
                  <span className="text-sm text-muted-foreground">
                    закрыто {data.plan.completed_count} из {data.plan.topic_count} тем
                  </span>
                </div>
                <Progress value={Math.round(data.plan.progress * 100)} />
                <Link
                  to={`/plans/${data.plan.id}`}
                  className={buttonVariants({ variant: 'outline' })}
                >
                  Открыть план
                </Link>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-muted-foreground">
                  План строится по пробелам вакансии, слабым и незатронутым темам
                  интервью.
                </p>
                <Link
                  to={data.vacancy ? `/vacancies/${data.vacancy.id}` : '/profile'}
                  className={buttonVariants({ variant: 'outline' })}
                >
                  {data.vacancy ? 'Построить план' : 'Открыть профиль'}
                </Link>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>История интервью</CardTitle>
          <CardDescription>Последние завершённые тренировки.</CardDescription>
        </CardHeader>
        <CardContent>
          {data.interview_history.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              История появится после первого интервью.
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {data.interview_history.map((item) => (
                <Link
                  key={item.id}
                  to={`/reports/${item.id}`}
                  className="flex flex-col gap-1 rounded-md p-2 transition-colors hover:bg-muted/50"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium">
                      {item.vacancy_title ?? 'Интервью'}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {item.finished_at ? formatDate(item.finished_at) : '—'} ·{' '}
                      {item.level ?? 0}/100
                    </span>
                  </div>
                  <Progress value={Math.round(item.score ?? 0)} />
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string
  value: number
  hint: string
}) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-1 pt-4">
        <span className="text-3xl font-medium">{value}</span>
        <span className="text-sm font-medium">{label}</span>
        <span className="text-xs text-muted-foreground">{hint}</span>
      </CardContent>
    </Card>
  )
}

function ReadinessCard({
  data,
  vacancies,
  onSelect,
}: {
  data: DashboardRead
  vacancies: { id: string; title?: string | null; company?: string | null }[]
  onSelect: (id: string) => void
}) {
  const vacancy = data.vacancy
  if (!vacancy) {
    return null
  }
  const coverage = Math.round(vacancy.coverage * 100)
  const critical =
    typeof vacancy.critical_readiness === 'number'
      ? Math.round(vacancy.critical_readiness * 100)
      : null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Готовность к вакансии</CardTitle>
        <CardDescription>
          {vacancy.title ?? 'Без названия'}
          {vacancy.company ? ` · ${vacancy.company}` : ''}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {vacancies.length > 1 ? (
          <div className="flex flex-wrap gap-2">
            {vacancies.map((item) => (
              <Button
                key={item.id}
                size="sm"
                variant={item.id === vacancy.id ? 'default' : 'outline'}
                onClick={() => onSelect(item.id)}
              >
                {item.title ?? 'Без названия'}
              </Button>
            ))}
          </div>
        ) : null}

        <div className="grid gap-6 sm:grid-cols-3">
          <div className="flex flex-col gap-1">
            <span className="text-4xl font-medium">{coverage}%</span>
            <span className="text-sm text-muted-foreground">
              готовность по вакансии
            </span>
            <Progress value={coverage} />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-4xl font-medium">
              {critical === null ? '—' : `${critical}%`}
            </span>
            <span className="text-sm text-muted-foreground">
              обязательные требования закрыты
            </span>
            {critical !== null ? <Progress value={critical} /> : null}
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-4xl font-medium">
              {Math.round(vacancy.average_gap)}
            </span>
            <span className="text-sm text-muted-foreground">
              средний разрыв, пункты
            </span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
          <span>
            {vacancy.satisfied_count} из {vacancy.requirements_count} требований закрыто
          </span>
          <span>·</span>
          <span>{vacancy.critical_gap_count} обязательных с разрывом</span>
        </div>

        {vacancy.focus_topics.length > 0 ? (
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">Фокус развития</span>
            <div className="flex flex-col gap-2">
              {vacancy.focus_topics.map((item) => (
                <div
                  key={item.topic_key ?? item.skill_name}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-2"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm">
                      {item.topic_name ?? item.skill_name}
                    </span>
                    <Badge
                      variant={item.criticality === 'must_have' ? 'default' : 'outline'}
                    >
                      {item.criticality === 'must_have' ? 'обязательно' : 'желательно'}
                    </Badge>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {item.current_level} из {item.required_level} · не хватает {item.gap}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Link
            to={`/vacancies/${vacancy.id}`}
            className={buttonVariants({ variant: 'outline' })}
          >
            Открыть вакансию
          </Link>
          <Link
            to={`/profile?vacancy=${vacancy.id}`}
            className={buttonVariants({ variant: 'outline' })}
          >
            Разрывы в профиле
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
