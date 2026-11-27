const SOURCE_LABELS: Record<string, string> = {
  manual: 'вручную',
  interview: 'интервью',
  test: 'тест',
  resume: 'резюме',
}

const MATCH_LABELS: Record<string, string> = {
  exact: 'точное',
  alias: 'синоним',
  fuzzy: 'нечёткое',
  embedding: 'эмбеддинг',
  provisional: 'новая тема',
  auto_approve: 'авто-подтверждено',
  auto_merge: 'авто-объединено',
  backfill: 'восстановлено',
  none: 'не сопоставлено',
}

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source
}

export function matchMethodLabel(method: string): string {
  return MATCH_LABELS[method] ?? method
}

const BAND_LABELS: Record<string, string> = {
  ready: 'Готов',
  almost: 'Почти готов',
  needs_confirmation: 'Нужно подтвердить',
  not_ready: 'Не готов',
}

const SKILL_STATUS_LABELS: Record<string, string> = {
  confirmed: 'подтверждён',
  partial: 'частично',
  self_only: 'только резюме',
  unverified: 'не проверен',
  not_tested: 'не пройден',
}

export function bandLabel(band: string): string {
  return BAND_LABELS[band] ?? band
}

export function skillStatusLabel(status: string): string {
  return SKILL_STATUS_LABELS[status] ?? status
}

export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—'
  }
  return `${Math.round(value * 100)}%`
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(iso))
}
