import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { ApiError, createPlan } from '@/api/client'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { useAuthToken } from '@/lib/useAuthToken'

export function CreatePlanButton({
  vacancyId,
  label = 'Построить план подготовки',
}: {
  vacancyId?: string | null
  label?: string
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { token, expire } = useAuthToken()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleClick() {
    if (token === null) {
      navigate('/login')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const plan = await createPlan({ vacancy_id: vacancyId ?? null }, token)
      await queryClient.invalidateQueries({ queryKey: ['plans'] })
      navigate(`/plans/${plan.id}`)
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

  return (
    <div className="flex flex-col gap-1">
      <Button type="button" onClick={handleClick} disabled={busy}>
        {busy ? 'Строим план…' : label}
      </Button>
      {error ? <span className="text-xs text-destructive">{error}</span> : null}
    </div>
  )
}
