import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import {
  ApiError,
  createResume,
  createVacancy,
  runAnalysis,
  type AnalysisResponse,
  type GapAnalysisRead,
  type SkillRead,
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import { matchMethodLabel } from '@/lib/labels'
import { useAuthToken } from '@/lib/useAuthToken'

type Stage = 'vacancy' | 'resume' | 'analysis'

const STAGE_LABELS: Record<Stage, string> = {
  vacancy: 'Анализируем вакансию…',
  resume: 'Анализируем резюме…',
  analysis: 'Считаем разрывы…',
}

export default function VacancyUploadPage() {
  const queryClient = useQueryClient()
  const { token, expire } = useAuthToken()
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [vacancyText, setVacancyText] = useState('')
  const [resumeText, setResumeText] = useState('')
  const [stage, setStage] = useState<Stage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (token === null) {
      return
    }
    if (vacancyText.trim() === '' || resumeText.trim() === '') {
      setError('Вставьте текст вакансии и резюме.')
      return
    }

    setError(null)
    setAnalysis(null)
    try {
      setStage('vacancy')
      const vacancy = await createVacancy(
        {
          title: title.trim() || null,
          company: company.trim() || null,
          raw_text: vacancyText.trim(),
        },
        token,
      )

      setStage('resume')
      const resume = await createResume({ raw_text: resumeText.trim() }, token)

      setStage('analysis')
      const result = await runAnalysis(
        { vacancy_id: vacancy.id, resume_id: resume.id },
        token,
      )
      setAnalysis(result)

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['profile'] }),
        queryClient.invalidateQueries({ queryKey: ['vacancies'] }),
      ])
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        expire()
        return
      }
      setError(errorMessage(err))
    } finally {
      setStage(null)
    }
  }

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Новая подготовка</CardTitle>
          <CardDescription>Войдите, чтобы загрузить вакансию и резюме.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  const submitting = stage !== null

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Новая подготовка</CardTitle>
          <CardDescription>
            Вставьте текст вакансии и резюме — AgentHR извлечёт навыки, соберёт профиль
            знаний и покажет разрывы.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
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
                rows={8}
                placeholder="Скопируйте описание вакансии: обязанности, требования, технологии."
                value={vacancyText}
                onChange={(event) => setVacancyText(event.target.value)}
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="resume-text">Текст резюме</Label>
              <Textarea
                id="resume-text"
                required
                rows={8}
                placeholder="Вставьте текст резюме: опыт, проекты, технологии."
                value={resumeText}
                onChange={(event) => setResumeText(event.target.value)}
              />
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}

            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={submitting}>
                {stage ? STAGE_LABELS[stage] : 'Анализировать'}
              </Button>
              {analysis ? (
                <Button type="button" variant="outline" onClick={() => setAnalysis(null)}>
                  Скрыть результат
                </Button>
              ) : null}
              <span className="text-xs text-muted-foreground">
                Парсинг PDF/DOCX не поддерживается — только текст.
              </span>
            </div>
          </form>
        </CardContent>
      </Card>

      {analysis ? <AnalysisResult analysis={analysis} /> : null}
    </div>
  )
}

function AnalysisResult({ analysis }: { analysis: AnalysisResponse }) {
  const { vacancy, resume, gaps } = analysis
  const readiness = Math.round(gaps.overall_readiness * 100)
  const satisfied = gaps.items.filter((item) => item.satisfied).length

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Готовность к вакансии</CardTitle>
          <CardDescription>
            {vacancy.title ?? 'Без названия'}
            {vacancy.company ? ` · ${vacancy.company}` : ''}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex items-end justify-between">
            <span className="text-3xl font-medium">{readiness}%</span>
            <span className="text-sm text-muted-foreground">
              {satisfied} из {gaps.items.length} требований закрыто
            </span>
          </div>
          <Progress value={readiness} />
          {gaps.unmatched_count > 0 ? (
            <p className="text-sm text-muted-foreground">
              {gaps.unmatched_count} навык(ов) вне онтологии — показаны в разрывах,
              но не входят в готовность.
            </p>
          ) : null}
          <div>
            <Link to="/profile" className={buttonVariants({ variant: 'outline' })}>
              Открыть профиль знаний
            </Link>
          </div>
        </CardContent>
      </Card>

      <SkillsCard title="Требования вакансии" skills={vacancy.skills} showWeight />

      <GapsCard gaps={gaps} />

      <SkillsCard title="Навыки из резюме" skills={resume.skills} />
    </div>
  )
}

function SkillsCard({
  title,
  skills,
  showWeight = false,
}: {
  title: string
  skills: SkillRead[]
  showWeight?: boolean
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {skills.length === 0 ? (
          <p className="text-sm text-muted-foreground">Навыки не найдены.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Навык</TableHead>
                <TableHead>Тема</TableHead>
                <TableHead>Уровень</TableHead>
                {showWeight ? <TableHead>Вес</TableHead> : null}
                <TableHead>Метод</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {skills.map((skill) => (
                <TableRow key={skill.id}>
                  <TableCell>{skill.raw_name}</TableCell>
                  <TableCell>
                    {skill.topic ? (
                      skill.topic.name
                    ) : (
                      <Badge variant="secondary">вне онтологии</Badge>
                    )}
                  </TableCell>
                  <TableCell>{skill.level}</TableCell>
                  {showWeight ? (
                    <TableCell>
                      {skill.weight === null || skill.weight === undefined
                        ? '—'
                        : skill.weight.toFixed(2)}
                    </TableCell>
                  ) : null}
                  <TableCell className="text-muted-foreground">
                    {matchMethodLabel(skill.match_method)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

function GapsCard({ gaps }: { gaps: GapAnalysisRead }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Разрывы</CardTitle>
        <CardDescription>
          Чем больше разрыв, тем важнее тема для подготовки.
        </CardDescription>
      </CardHeader>
      <CardContent>
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
                <TableHead>Статус</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {gaps.items.map((item) => (
                <TableRow key={item.skill_name}>
                  <TableCell>{item.skill_name}</TableCell>
                  <TableCell>
                    {item.topic_name ?? (
                      <Badge variant="outline">вне онтологии</Badge>
                    )}
                  </TableCell>
                  <TableCell>{item.required_level}</TableCell>
                  <TableCell>{item.user_level}</TableCell>
                  <TableCell>{item.gap}</TableCell>
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
      </CardContent>
    </Card>
  )
}
