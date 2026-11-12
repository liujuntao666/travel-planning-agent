import type {
  ChatResult,
  ConversationDetail,
  ConversationSummary,
  ExportRecord,
  PoiOption,
  StreamHandler,
  StyleOption,
  Trip,
  User,
  VersionCompare,
  VersionInfo,
} from './types'
import {
  API_BASE,
  API_ORIGIN,
  getToken,
  newRequestId,
  request,
  resolveFileUrl,
  setToken,
} from './http'

export { API_BASE, API_ORIGIN, resolveFileUrl }

interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

interface LoginResult extends User {
  access_token: string
  token_type: string
  expires_in: number
  role?: string
}

export interface CaptchaResult {
  captcha_id: string
  image: string
  expires_in: number
  debug_code?: string
}

export interface AuthSession {
  user: User
  access_token: string
  token_type: string
  expires_in: number
  roles: string[]
  permissions: string[]
  menus: unknown[]
  is_admin: boolean
}

export interface PasswordLoginPayload {
  username: string
  password: string
  captcha_id: string
  captcha_code: string
}

export interface RegisterPayload extends PasswordLoginPayload {
  nickname?: string | null
  email?: string | null
  phone?: string | null
}

export const api = {
  login: async (openId: string, nickname?: string) => {
    const data = await request<LoginResult>('/users/login', {
      method: 'POST',
      data: { open_id: openId, nickname: nickname || null, source: 'APP' },
    })
    setToken(data.access_token)
    return data
  },

  captcha: () => request<CaptchaResult>('/auth/captcha'),

  passwordLogin: async (payload: PasswordLoginPayload) => {
    const data = await request<AuthSession>('/auth/login', { method: 'POST', data: payload })
    setToken(data.access_token)
    return data
  },

  register: async (payload: RegisterPayload) => {
    const data = await request<AuthSession>('/auth/register', { method: 'POST', data: payload })
    setToken(data.access_token)
    return data
  },

  me: () => request<AuthSession>('/auth/me'),

  forgotPassword: (account: string, captchaId: string, captchaCode: string) =>
    request<{ message: string; expires_in: number; reset_token: string | null }>(
      '/auth/password/forgot',
      { method: 'POST', data: { account, captcha_id: captchaId, captcha_code: captchaCode } },
    ),

  resetPassword: (resetToken: string, newPassword: string) =>
    request<{ message: string }>('/auth/password/reset', {
      method: 'POST',
      data: { reset_token: resetToken, new_password: newPassword },
    }),

  logout: () => request<{ message: string }>('/auth/logout', { method: 'POST' }),

  createConversation: (userId: number, title?: string) =>
    request<{ id: number; user_id: number; title: string | null }>('/conversations', {
      method: 'POST',
      data: { user_id: userId, title: title || null },
    }),

  listConversations: async (userId: number) => {
    const page = await request<PageResult<ConversationSummary>>('/conversations', {
      params: { user_id: userId, page: 1, page_size: 50, sort: 'id:desc' },
    })
    return page.items
  },

  conversationDetail: (conversationId: number) =>
    request<ConversationDetail>(`/conversations/${conversationId}`),

  sendMessage: (conversationId: number, content: string, startDate?: string | null) =>
    request<ChatResult>(`/conversations/${conversationId}/messages`, {
      method: 'POST',
      data: { content, start_date: startDate || null },
    }),

  getTrip: (tripId: number) => request<Trip>(`/trips/${tripId}`),

  versions: async (tripId: number) => {
    const page = await request<PageResult<VersionInfo>>(`/trips/${tripId}/versions`, {
      params: { page: 1, page_size: 100, sort: 'version_no:desc' },
    })
    return page.items
  },

  versionDetail: (tripId: number, versionId: number) =>
    request<Trip>(`/trips/${tripId}/versions/${versionId}`),

  compareVersions: (tripId: number, base: number, target: number) =>
    request<VersionCompare>(`/trips/${tripId}/versions/compare`, {
      params: { base, target },
    }),

  activateVersion: (tripId: number, versionId: number) =>
    request<Trip>(`/trips/${tripId}/versions/${versionId}/activate`, { method: 'POST' }),

  updateItem: (
    tripId: number,
    itemId: number,
    payload: { start_time?: string; end_time?: string; period?: string; note?: string },
  ) =>
    request<Trip>(`/trips/${tripId}/items/${itemId}`, {
      method: 'PATCH',
      data: payload,
    }),

  deleteItem: (tripId: number, itemId: number) =>
    request<Trip>(`/trips/${tripId}/items/${itemId}`, { method: 'DELETE' }),

  moveItem: (tripId: number, itemId: number, direction: 'up' | 'down') =>
    request<Trip>(`/trips/${tripId}/items/${itemId}/move`, {
      method: 'POST',
      data: { direction },
    }),

  addItem: (
    tripId: number,
    payload: {
      day_index: number
      item_type?: string
      ref_id?: number | null
      ref_name?: string | null
      start_time?: string
      end_time?: string
      duration_min?: number
      period?: string
      note?: string
    },
  ) =>
    request<Trip>(`/trips/${tripId}/items`, {
      method: 'POST',
      data: payload,
    }),

  replaceHotel: (tripId: number, lodgingId: number, hotelId: number) =>
    request<Trip>(`/trips/${tripId}/lodgings/${lodgingId}/replace`, {
      method: 'POST',
      data: { hotel_id: hotelId },
    }),

  replan: (tripId: number) =>
    request<Trip>(`/trips/${tripId}/replan`, { method: 'POST' }),

  createExport: (tripId: number, format: 'PDF' | 'LONG_IMAGE' | 'WECHAT_ARTICLE') =>
    request<ExportRecord>(`/trips/${tripId}/exports`, {
      method: 'POST',
      data: { format },
    }),

  listExports: async (tripId: number) => {
    const page = await request<PageResult<ExportRecord>>(`/trips/${tripId}/exports`, {
      params: { page: 1, page_size: 100, sort: 'id:desc' },
    })
    return page.items
  },

  styles: () => request<StyleOption[]>('/meta/styles'),

  cities: () => request<string[]>('/resources/cities'),

  pois: async (city?: string, keyword?: string) => {
    const page = await request<PageResult<PoiOption>>('/resources/pois', {
      params: { city: city || undefined, keyword: keyword || undefined, page: 1, page_size: 100 },
    })
    return page.items
  },
}

export async function streamMessage(
  conversationId: number,
  content: string,
  startDate: string | null,
  onEvent: StreamHandler,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken()
  const res = await fetch(`${API_BASE}/conversations/${conversationId}/messages/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      'Idempotency-Key': newRequestId(),
    },
    body: JSON.stringify({ content, start_date: startDate || null }),
    signal,
  })
  if (!res.ok || !res.body) {
    let message = `流式请求失败（HTTP ${res.status}）`
    try {
      const data = (await res.json()) as { message?: string }
      message = data.message || message
    } catch {
      // ignore
    }
    throw new Error(message)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep = buffer.indexOf('\n\n')
    while (sep >= 0) {
      const raw = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      let event = 'message'
      const dataLines: string[] = []
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      if (dataLines.length) {
        try {
          onEvent(event, JSON.parse(dataLines.join('\n')) as Record<string, unknown>)
        } catch {
          // 忽略无法解析的事件
        }
      }
      sep = buffer.indexOf('\n\n')
    }
  }
}
