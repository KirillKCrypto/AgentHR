const SOURCE_LABELS: Record<string, string> = {
  manual: 'вручную',
  interview: 'интервью',
  assessment: 'оценка',
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

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(iso))
}
