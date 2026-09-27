import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'

import { ApiError, login, register } from '@/api/client'
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
import { saveTokens } from '@/lib/tokens'

type Mode = 'login' | 'register'

function errorMessage(error: unknown, mode: Mode): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Неверный email или пароль.'
    }
    if (error.status === 409) {
      return 'Пользователь с таким email уже зарегистрирован.'
    }
    if (error.status === 422) {
      return 'Проверьте email и пароль: пароль не короче 8 символов.'
    }
    return `Ошибка сервера: HTTP ${error.status}.`
  }
  return mode === 'login'
    ? 'Не удалось войти. Попробуйте ещё раз.'
    : 'Не удалось зарегистрироваться. Попробуйте ещё раз.'
}

export default function LoginPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'register') {
        await register({ email, password })
      }
      const tokens = await login({ email, password })
      saveTokens(tokens)
      navigate('/')
    } catch (err) {
      setError(errorMessage(err, mode))
    } finally {
      setSubmitting(false)
    }
  }

  function switchMode() {
    setMode(mode === 'login' ? 'register' : 'login')
    setError(null)
  }

  return (
    <div className="mx-auto max-w-sm">
      <Card>
        <CardHeader>
          <CardTitle>
            {mode === 'login' ? 'Вход в AgentHR' : 'Регистрация в AgentHR'}
          </CardTitle>
          <CardDescription>
            {mode === 'login'
              ? 'Введите email и пароль, чтобы продолжить.'
              : 'Создайте аккаунт: пароль — не короче 8 символов.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Пароль</Label>
              <Input
                id="password"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                minLength={mode === 'register' ? 8 : undefined}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Подождите…' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
            </Button>
            <Button type="button" variant="ghost" disabled={submitting} onClick={switchMode}>
              {mode === 'login'
                ? 'Нет аккаунта? Зарегистрироваться'
                : 'Уже есть аккаунт? Войти'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
