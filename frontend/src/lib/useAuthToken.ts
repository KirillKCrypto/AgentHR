import { useCallback, useState } from 'react'

import { clearTokens, getAccessToken } from '@/lib/tokens'

/** Access-токен из localStorage с возможностью сбросить сессию при 401. */
export function useAuthToken() {
  const [token, setToken] = useState<string | null>(() => getAccessToken())

  const expire = useCallback(() => {
    clearTokens()
    setToken(null)
  }, [])

  return { token, expire }
}
