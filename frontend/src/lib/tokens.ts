const ACCESS_TOKEN_KEY = 'agenthr.access_token'
const REFRESH_TOKEN_KEY = 'agenthr.refresh_token'

export function saveTokens(tokens: { access_token: string; refresh_token: string }): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}
