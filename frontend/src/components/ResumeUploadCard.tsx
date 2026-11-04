import { useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type FormEvent } from 'react'

import { ApiError, createResume, uploadResume } from '@/api/client'
import { Button } from '@/components/ui/button'
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
import { errorMessage } from '@/lib/errors'

const MAX_FILE_BYTES = 5 * 1024 * 1024

type Mode = 'file' | 'text'

export function ResumeUploadCard({
  token,
  onUnauthorized,
}: {
  token: string
  onUnauthorized: () => void
}) {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<Mode>('file')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSuccess(null)

    if (mode === 'text' && text.trim() === '') {
      setError('Вставьте текст резюме.')
      return
    }
    if (mode === 'file' && file === null) {
      setError('Выберите файл PDF или DOCX.')
      return
    }
    if (file !== null && file.size > MAX_FILE_BYTES) {
      setError('Файл больше 5 МБ. Загрузите текст вручную.')
      return
    }

    setBusy(true)
    try {
      const resume =
        mode === 'file' && file !== null
          ? await uploadResume(file, token, title)
          : await createResume({ raw_text: text.trim(), title: title.trim() || null }, token)

      await queryClient.invalidateQueries({ queryKey: ['profile'] })
      setSuccess(
        `Резюме сохранено. Извлечено навыков: ${resume.skills.length}. ` +
          'Профиль обновлён — проверьте навыки в блоке ниже.',
      )
      setText('')
      setFile(null)
      if (fileInput.current) {
        fileInput.current.value = ''
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized()
        return
      }
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Загрузить резюме</CardTitle>
        <CardDescription>
          Шаг 1. Загрузите файл PDF/DOCX или вставьте текст — AgentHR извлечёт навыки и
          обновит профиль знаний.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={mode === 'file' ? 'default' : 'outline'}
              onClick={() => setMode('file')}
            >
              Файл PDF/DOCX
            </Button>
            <Button
              type="button"
              size="sm"
              variant={mode === 'text' ? 'default' : 'outline'}
              onClick={() => setMode('text')}
            >
              Текст
            </Button>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="resume-title">Название резюме</Label>
            <Input
              id="resume-title"
              placeholder="Например, Backend-разработчик"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>

          {mode === 'file' ? (
            <div className="flex flex-col gap-2">
              <Label htmlFor="resume-file">Файл резюме</Label>
              <Input
                id="resume-file"
                ref={fileInput}
                type="file"
                accept=".pdf,.docx"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              <span className="text-xs text-muted-foreground">
                {file
                  ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} МБ`
                  : 'PDF или DOCX до 5 МБ. Файл не сохраняется — только текст.'}
              </span>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <Label htmlFor="resume-text">Текст резюме</Label>
              <Textarea
                id="resume-text"
                rows={8}
                placeholder="Опыт, проекты, технологии."
                value={text}
                onChange={(event) => setText(event.target.value)}
              />
            </div>
          )}

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {success ? <p className="text-sm text-muted-foreground">{success}</p> : null}

          <div>
            <Button type="submit" disabled={busy}>
              {busy ? 'Извлекаем навыки…' : 'Извлечь навыки'}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
