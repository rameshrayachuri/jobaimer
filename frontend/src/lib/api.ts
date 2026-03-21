/**
 * Typed API client for JobAimer backend.
 * Access token stored in memory only (security rule S4).
 */
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

let _accessToken: string | null = null

export function setAccessToken(token: string | null) { _accessToken = token }
export function getAccessToken() { return _accessToken }

type RequestOptions = {
  method?: string
  body?: unknown
  signal?: AbortSignal
  rawBody?: BodyInit
}

class ApiError extends Error {
  constructor(public status: number, message: string, public data?: unknown) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, rawBody } = opts

  const headers: Record<string, string> = {}
  if (_accessToken) headers['Authorization'] = `Bearer ${_accessToken}`
  if (body) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: rawBody ?? (body ? JSON.stringify(body) : undefined),
    credentials: 'include', // for refresh token cookie
    signal,
  })

  if (!res.ok) {
    let errData: unknown
    try { errData = await res.json() } catch { errData = await res.text() }
    const detail = typeof errData === 'object' && errData !== null && 'detail' in errData
      ? String((errData as { detail: unknown }).detail)
      : res.statusText
    throw new ApiError(res.status, detail, errData)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const auth = {
  signUp: (body: { email: string; password: string; phone: string; full_name: string }) =>
    request<{ user_id: string; message: string }>('/auth/sign-up', { method: 'POST', body }),

  signIn: (identifier: string, password: string) =>
    request<{ access_token: string; refresh_token: string; user: { id: string; email: string } }>(
      '/auth/sign-in', { method: 'POST', body: { identifier, password } }
    ),

  verifyOtp: (phone: string, code: string) =>
    request<{ access_token: string; refresh_token: string }>('/auth/otp/verify',
      { method: 'POST', body: { phone, code } }),

  sendOtp: (phone: string) =>
    request<{ message: string }>('/auth/otp/send', { method: 'POST', body: { phone } }),

  refresh: () =>
    request<{ access_token: string }>('/auth/refresh', { method: 'POST', body: {} }),

  signOut: () => request<void>('/auth/sign-out', { method: 'POST' }),
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const dashboard = {
  get: () => request<DashboardData>('/api/v1/dashboard'),
}

// ── Applications ──────────────────────────────────────────────────────────────
export const applications = {
  list: (params?: { status?: string; page?: number; page_size?: number }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<ApplicationsResponse>(`/api/v1/applications${q ? `?${q}` : ''}`)
  },
  get: (id: string) => request<Application>(`/api/v1/applications/${id}`),
  stats: () => request<ApplicationStats>('/api/v1/applications/stats'),
  patch: (id: string, body: Partial<{ status: string; user_notes: string }>) =>
    request(`/api/v1/applications/${id}`, { method: 'PATCH', body }),
  delete: (id: string) => request<DeleteResult>(`/api/v1/applications/${id}`, { method: 'DELETE' }),
  deleteResume: (id: string) => request<DeleteResult>(`/api/v1/applications/${id}/resume`, { method: 'DELETE' }),
  resumeStatus: (id: string) => request<ResumeStatus>(`/api/v1/applications/${id}/resume/status`),
}

// ── Profile ───────────────────────────────────────────────────────────────────
export const profile = {
  get: () => request<UserProfile>('/api/v1/profile'),
  update: (body: Partial<UserProfile>) => request('/api/v1/profile', { method: 'PUT', body }),
  uploadResume: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ resume_version_id: string; parsed_data: unknown }>(
      '/api/v1/profile/resume', { method: 'POST', rawBody: form }
    )
  },
}

// ── Agent ─────────────────────────────────────────────────────────────────────
export const agent = {
  status: () => request<AgentStatus>('/api/v1/agent/status'),
  activate: () => request('/api/v1/agent/activate', { method: 'POST' }),
  pause: () => request('/api/v1/agent/pause', { method: 'POST' }),
  stop: () => request('/api/v1/agent/stop', { method: 'POST' }),
}

// ── Billing ───────────────────────────────────────────────────────────────────
export const billing = {
  subscription: () => request<SubscriptionData>('/api/v1/billing/subscription'),
  checkout: (plan_id: string, promo_code?: string) =>
    request<{ checkout_url: string }>('/api/v1/billing/checkout',
      { method: 'POST', body: { plan_id, promo_code } }),
  portal: () => request<{ portal_url: string }>('/api/v1/billing/portal', { method: 'POST' }),
  invoices: () => request<{ invoices: Invoice[] }>('/api/v1/billing/invoices'),
  validateCoupon: (code: string, plan_id?: string) =>
    request<CouponValidation>('/api/v1/billing/coupons/validate',
      { method: 'POST', body: { code, plan_id } }),
}

// ── Types ─────────────────────────────────────────────────────────────────────
export interface DashboardData {
  total_applied: number
  interviews_scheduled: number
  offers_received: number
  offers_accepted: number
  avg_ats_score: number
  this_week_applied: number
  agent_status: string
  next_cycle_at: string | null
  subscription: SubscriptionData | null
  recent_applications: Application[]
}

export interface Application {
  id: string
  status: string
  applied_at: string | null
  ats_score: number | null
  quick_score: number | null
  user_notes: string | null
  confirmation_id: string | null
  manual_apply_url: string | null
  resume: { available: boolean; ats_score: number | null; version: string | null }
  job: { title: string; company: string; location: string; portal: string }
}

export interface ApplicationsResponse {
  applications: Application[]
  page: number
  page_size: number
}

export interface ApplicationStats {
  total_applied: number; interviews: number; offers: number
  accepted: number; avg_ats_score: number; this_week: number
}

export interface DeleteResult {
  deleted: boolean; resume_also_deleted?: boolean; bytes_freed?: number
}

export interface ResumeStatus {
  available: boolean; deleted_at: string | null; deletion_reason: string | null
}

export interface UserProfile {
  user_id: string; full_name: string; email: string; phone: string
  location: string; linkedin_url: string; github_url: string
  target_titles: string[]; preferred_locations: string[]
  remote_preference: string; salary_min: number; salary_max: number
  excluded_companies: string[]; seniority_level: string
  agent_status: string; onboarding_complete: boolean
}

export interface AgentStatus {
  status: string; last_cycle_at: string | null; next_cycle_at: string | null
}

export interface SubscriptionData {
  plan_id: string; status: string; trial_end: string | null
  current_period_end: string | null; cancel_at_period_end: boolean
  plan: { name: string; max_apps_per_cycle: number; max_portals: number
          cover_letter_enabled: boolean; sms_alerts_enabled: boolean }
}

export interface Invoice {
  amount_paid: number; currency: string; status: string
  pdf_url: string; period_start: string; paid_at: string
}

export interface CouponValidation {
  valid: boolean; code: string; discount_type: string
  percent_off: number | null; amount_off_cents: number | null
  duration: string; original_price_cents: number
  discounted_price_cents: number; savings_cents: number; savings_label: string
}
