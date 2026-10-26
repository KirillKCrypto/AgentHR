import { ApiError } from '@/api/client'

/** Понятное пользователю сообщение об ошибке API. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Сессия истекла — войдите заново.'
    }
    if (error.status === 422) {
      return error.message.startsWith('HTTP ') ? 'Проверьте введённые данные.' : error.message
    }
    if (error.status === 502) {
      return 'LLM недоступна — попробуйте ещё раз.'
    }
    return `Ошибка сервера: HTTP ${error.status}.`
  }
  return 'Не удалось выполнить запрос. Проверьте соединение.'
}
