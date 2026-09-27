import type { components } from './schema'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export type LoginRequest = components['schemas']['LoginRequest']
export type RegisterRequest = components['schemas']['RegisterRequest']
export type TokenResponse = components['schemas']['TokenResponse']
export type UserRead = components['schemas']['UserRead']

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface ApiFetchOptions extends RequestInit {
  token?: string | null
}

async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { token, headers, ...rest } = options
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  })

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (typeof body === 'object' && body !== null && 'detail' in body) {
      const { detail } = body as { detail: unknown }
      if (typeof detail === 'string') {
        return detail
      }
    }
  } catch {
    // тело не JSON — вернём статус ниже
  }
  return `HTTP ${response.status}`
}

export function login(payload: LoginRequest): Promise<TokenResponse> {
  return apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(payload) })
}

export function register(payload: RegisterRequest): Promise<UserRead> {
  return apiFetch('/auth/register', { method: 'POST', body: JSON.stringify(payload) })
}

export function fetchMe(token: string): Promise<UserRead> {
  return apiFetch('/me', { token })
}
