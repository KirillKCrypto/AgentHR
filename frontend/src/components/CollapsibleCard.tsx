import { ChevronDown } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/**
 * Карточка с раскрывающимся содержимым.
 * Состояние запоминается в localStorage, если задан storageKey.
 */
export function CollapsibleCard({
  title,
  description,
  storageKey,
  defaultOpen = true,
  id,
  children,
}: {
  title: ReactNode
  description?: ReactNode
  storageKey?: string
  defaultOpen?: boolean
  id?: string
  children: ReactNode
}) {
  const contentId = useId()
  const [open, setOpen] = useState(() => {
    if (!storageKey || typeof window === 'undefined') {
      return defaultOpen
    }
    const saved = window.localStorage.getItem(`collapsible:${storageKey}`)
    return saved === null ? defaultOpen : saved === '1'
  })

  function toggle() {
    setOpen((current) => {
      const next = !current
      if (storageKey && typeof window !== 'undefined') {
        window.localStorage.setItem(`collapsible:${storageKey}`, next ? '1' : '0')
      }
      return next
    })
  }

  return (
    <Card id={id}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
        <CardAction>
          <button
            type="button"
            onClick={toggle}
            aria-expanded={open}
            aria-controls={contentId}
            className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <span>{open ? 'Свернуть' : 'Развернуть'}</span>
            <ChevronDown
              className={cn('size-4 transition-transform', open ? 'rotate-180' : '')}
            />
          </button>
        </CardAction>
      </CardHeader>
      {open ? <CardContent id={contentId}>{children}</CardContent> : null}
    </Card>
  )
}
