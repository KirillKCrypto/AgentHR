import { useState } from 'react'
import { useNavigate } from 'react-router'

import { ApiError, createInterview } from '@/api/client'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { useAuthToken } from '@/lib/useAuthToken'

export function StartInterviewButton({
  planId,
  vacancyId,
}: {
  planId?: string
  vacancyId?: string
}) {
  const navigate = useNavigate()
  const { token, expire } = useAuthToken()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function start() {
    if (token === null) {
      navigate('/login')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const interview = await createInterview(
        vacancyId ? { vacancy_id: vacancyId } : { plan_id: planId },
        token,
      )
      navigate(`/interviews/${interview.id}`)
    } catch (value) {
      if (value instanceof ApiError && value.status === 401) {
        expire()
        return
      }
      setError(errorMessage(value))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <Button type="button" onClick={() => void start()} disabled={busy}>
        {busy ? 'Готовим интервью…' : 'Пройти интервью'}
      </Button>
      {error ? <span className="text-xs text-destructive">{error}</span> : null}
    </div>
  )
}
