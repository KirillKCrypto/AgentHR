import type { components } from './schema'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export type LoginRequest = components['schemas']['LoginRequest']
export type RegisterRequest = components['schemas']['RegisterRequest']
export type TokenResponse = components['schemas']['TokenResponse']
export type UserRead = components['schemas']['UserRead']
export type VacancyCreate = components['schemas']['VacancyCreate']
export type VacancyRead = components['schemas']['VacancyRead']
export type VacancySummary = components['schemas']['VacancySummary']
export type ResumeCreate = components['schemas']['ResumeCreate']
export type ResumeRead = components['schemas']['ResumeRead']
export type ResumeSummary = components['schemas']['ResumeSummary']
export type SkillRead = components['schemas']['SkillRead']
export type ProfileRead = components['schemas']['ProfileRead']
export type GapAnalysisRead = components['schemas']['GapAnalysisRead']
export type AnalysisRequest = components['schemas']['AnalysisRequest']
export type AnalysisResponse = components['schemas']['AnalysisResponse']
export type PlanCreate = components['schemas']['PlanCreate']
export type PlanRead = components['schemas']['PlanRead']
export type PlanSummary = components['schemas']['PlanSummaryRead']
export type QuestionRead = components['schemas']['QuestionRead']
export type QuizRead = components['schemas']['QuizRead']
export type QuizResultRead = components['schemas']['QuizResultRead']
export type InterviewCreate = components['schemas']['InterviewCreate']
export type InterviewRead = components['schemas']['InterviewRead']
export type InterviewTurnRead = components['schemas']['InterviewTurnRead']
export type InterviewSummary = components['schemas']['InterviewSummaryRead']
export type InterviewAnswerRead = components['schemas']['InterviewAnswerRead']
export type InterviewReportRead = components['schemas']['InterviewReportRead']
export type InterviewReportTopicRead = components['schemas']['InterviewReportTopicRead']
export type DashboardRead = components['schemas']['DashboardRead']
export type PlanProgressRead = components['schemas']['PlanProgressRead']

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
  const isFormData = rest.body instanceof FormData
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
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

export function createVacancy(payload: VacancyCreate, token: string): Promise<VacancyRead> {
  return apiFetch('/vacancies', { method: 'POST', token, body: JSON.stringify(payload) })
}

export function fetchVacancy(vacancyId: string, token: string): Promise<VacancyRead> {
  return apiFetch(`/vacancies/${encodeURIComponent(vacancyId)}`, { token })
}

export function listVacancies(token: string): Promise<VacancySummary[]> {
  return apiFetch('/vacancies', { token })
}

export function createResume(payload: ResumeCreate, token: string): Promise<ResumeRead> {
  return apiFetch('/resumes', { method: 'POST', token, body: JSON.stringify(payload) })
}

export function uploadResume(file: File, token: string, title?: string): Promise<ResumeRead> {
  const form = new FormData()
  form.append('file', file)
  const trimmed = title?.trim()
  if (trimmed) {
    form.append('title', trimmed)
  }
  return apiFetch('/resumes/upload', { method: 'POST', token, body: form })
}

export function listResumes(token: string): Promise<ResumeSummary[]> {
  return apiFetch('/resumes', { token })
}

export function fetchProfile(token: string): Promise<ProfileRead> {
  return apiFetch('/profile', { token })
}

export function fetchGaps(vacancyId: string, token: string): Promise<GapAnalysisRead> {
  return apiFetch(`/profile/gaps?vacancy_id=${encodeURIComponent(vacancyId)}`, { token })
}

export function createPlan(payload: PlanCreate, token: string): Promise<PlanRead> {
  return apiFetch('/plans', { method: 'POST', token, body: JSON.stringify(payload) })
}

export function fetchPlan(planId: string, token: string): Promise<PlanRead> {
  return apiFetch(`/plans/${encodeURIComponent(planId)}`, { token })
}

export function fetchPlanProgress(
  planId: string,
  token: string,
): Promise<PlanProgressRead> {
  return apiFetch(`/plans/${encodeURIComponent(planId)}/progress`, { token })
}

export function fetchDashboard(
  token: string,
  vacancyId?: string | null,
): Promise<DashboardRead> {
  const query = vacancyId ? `?vacancy_id=${encodeURIComponent(vacancyId)}` : ''
  return apiFetch(`/dashboard${query}`, { token })
}

export function listPlans(token: string): Promise<PlanSummary[]> {
  return apiFetch('/plans', { token })
}

export function fetchQuestions(
  topicKey: string,
  token: string,
  options: { difficulty?: number; limit?: number } = {},
): Promise<QuestionRead[]> {
  const params = new URLSearchParams({ topic_key: topicKey })
  if (options.difficulty !== undefined) {
    params.set('difficulty', String(options.difficulty))
  }
  params.set('limit', String(options.limit ?? 5))
  return apiFetch(`/questions?${params.toString()}`, { token })
}

export function fetchTestQuestions(
  topicKey: string,
  token: string,
  count = 10,
): Promise<QuestionRead[]> {
  const params = new URLSearchParams({ topic_key: topicKey, count: String(count) })
  return apiFetch(`/questions/test?${params.toString()}`, { token })
}

export function fetchQuiz(topicKey: string, token: string, count = 10): Promise<QuizRead> {
  return apiFetch('/questions/quiz', {
    method: 'POST',
    token,
    body: JSON.stringify({ topic_key: topicKey, count }),
  })
}

export function gradeQuiz(
  topicKey: string,
  answers: { question_id: string; selected_option: number }[],
  token: string,
): Promise<QuizResultRead> {
  return apiFetch('/questions/quiz/grade', {
    method: 'POST',
    token,
    body: JSON.stringify({ topic_key: topicKey, answers }),
  })
}

export function fetchQuizResult(topicKey: string, token: string): Promise<QuizResultRead> {
  return apiFetch(`/questions/quiz/${encodeURIComponent(topicKey)}/result`, { token })
}

export function createInterview(
  payload: { vacancy_id: string },
  token: string,
): Promise<InterviewRead> {
  return apiFetch('/interviews', {
    method: 'POST',
    token,
    body: JSON.stringify(payload),
  })
}

export function fetchInterview(interviewId: string, token: string): Promise<InterviewRead> {
  return apiFetch(`/interviews/${encodeURIComponent(interviewId)}`, { token })
}

export function fetchInterviewReport(
  interviewId: string,
  token: string,
): Promise<InterviewReportRead> {
  return apiFetch(`/interviews/${encodeURIComponent(interviewId)}/report`, { token })
}

export function listInterviews(token: string): Promise<InterviewSummary[]> {
  return apiFetch('/interviews', { token })
}

export function answerInterview(
  interviewId: string,
  turnId: string,
  answerText: string,
  token: string,
): Promise<InterviewAnswerRead> {
  return apiFetch(`/interviews/${encodeURIComponent(interviewId)}/answers`, {
    method: 'POST',
    token,
    body: JSON.stringify({ turn_id: turnId, answer_text: answerText }),
  })
}

/** Читает SSE-поток интервью и передаёт события в onEvent. */
export async function streamInterviewAnswer(
  interviewId: string,
  turnId: string,
  answerText: string,
  token: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/interviews/${encodeURIComponent(interviewId)}/answers/stream`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ turn_id: turnId, answer_text: answerText }),
      signal,
    },
  )

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }
  if (!response.body) {
    throw new ApiError(0, 'Браузер не поддерживает потоковый ответ')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const handleFrame = (frame: string) => {
    let event = 'message'
    const dataLines: string[] = []
    for (const rawLine of frame.split('\n')) {
      const line = rawLine.replace(/\r$/, '')
      if (line.startsWith('event:')) {
        event = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
    if (dataLines.length === 0) {
      return
    }
    try {
      onEvent(event, JSON.parse(dataLines.join('\n')) as Record<string, unknown>)
    } catch {
      // повреждённый кадр не должен ломать весь поток
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    while (buffer.includes('\n\n')) {
      const boundary = buffer.indexOf('\n\n')
      const frame = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      handleFrame(frame)
    }
  }
}

export function runAnalysis(payload: AnalysisRequest, token: string): Promise<AnalysisResponse> {
  return apiFetch('/analysis', { method: 'POST', token, body: JSON.stringify(payload) })
}
