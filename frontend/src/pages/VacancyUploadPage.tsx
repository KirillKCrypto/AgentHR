import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import {
  ApiError,
  createVacancy,
  fetchGaps,
  fetchProfile,
  type GapAnalysisRead,
  type VacancyRead,
} from '@/api/client'
import { buttonVariants, Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { VacancyAssessment } from '@/components/VacancyAssessment'
import { errorMessage } from '@/lib/errors'
import { useAuthToken } from '@/lib/useAuthToken'

export default function VacancyUploadPage() {
  const queryClient = useQueryClient()
  const { token, expire } = useAuthToken()
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [vacancyText, setVacancyText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [vacancy, setVacancy] = useState<VacancyRead | null>(null)
  const [gaps, setGaps] = useState<GapAnalysisRead | null>(null)

  const profileQuery = useQuery({
    queryKey: ['profile', token],
    queryFn: () => fetchProfile(token as string),
    enabled: token !== null,
    retry: false,
  })

  useEffect(() => {
    if (profileQuery.error instanceof ApiError && profileQuery.error.status === 401) {
      expire()
    }
  }, [profileQuery.error, expire])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (token === null) {
      return
    }
    if (vacancyText.trim() === '') {
      setError('Вставьте текст вакансии.')
      return
    }

    setError(null)
    setVacancy(null)
    setGaps(null)
    setBusy(true)
    try {
      const created = await createVacancy(
        {
          title: title.trim() || null,
          company: company.trim() || null,
          raw_text: vacancyText.trim(),
        },
        token,
      )
      setVacancy(created)
      const report = await fetchGaps(created.id, token)
      setGaps(report)
      await queryClient.invalidateQueries({ queryKey: ['vacancies'] })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        expire()
        return
      }
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Проверка вакансии</CardTitle>
          <CardDescription>Войдите, чтобы проверить вакансию по своему профилю.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  const hasProfile = (profileQuery.data?.topics.length ?? 0) > 0

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Проверка вакансии</CardTitle>
          <CardDescription>
            Шаг 2. Вставьте описание вакансии — AgentHR извлечёт требования, сопоставит их с
            вашим профилем и покажет, каких уровней не хватает.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
            {!profileQuery.isPending && !hasProfile ? (
              <p className="text-sm text-muted-foreground">
                Профиль пока пуст. Сначала{' '}
                <Link to="/profile" className="underline underline-offset-4">
                  загрузите резюме
                </Link>
                , иначе все требования будут разрывами.
              </p>
            ) : null}

            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="vacancy-title">Название вакансии</Label>
                <Input
                  id="vacancy-title"
                  placeholder="Python-разработчик"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="vacancy-company">Компания</Label>
                <Input
                  id="vacancy-company"
                  placeholder="Acme"
                  value={company}
                  onChange={(event) => setCompany(event.target.value)}
                />
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="vacancy-text">Текст вакансии</Label>
              <Textarea
                id="vacancy-text"
                required
                rows={10}
                placeholder="Скопируйте описание вакансии: обязанности, требования, технологии."
                value={vacancyText}
                onChange={(event) => setVacancyText(event.target.value)}
              />
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}

            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={busy}>
                {busy ? 'Проверяем вакансию…' : 'Проверить вакансию'}
              </Button>
              <span className="text-xs text-muted-foreground">
                Парсинг файлов вакансии не поддерживается — только текст.
              </span>
            </div>
          </form>
        </CardContent>
      </Card>

      {vacancy && gaps ? (
        <VacancyAssessment vacancy={vacancy} gaps={gaps} hasProfile={hasProfile} />
      ) : null}
    </div>
  )
}
