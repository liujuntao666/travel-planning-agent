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

const RAW_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || 'http://127.0.0.1:8000/api/v1'

export const API_BASE = RAW_BASE.replace(/\/+$/, '')
export const API_ORIGIN = API_BASE.replace(/\/api\/v1$/, '')

export function resolveFileUrl(url?: string | null): string {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  return `${API_ORIGIN}${url.startsWith('/') ? url : `/${url}`}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    let message = `请求失败（HTTP ${res.status}）`
    try {
      const data = (await res.json()) as { message?: string; detail?: string }
      message = data.message || data.detail || message
    } catch {
      // 非 JSON 响应，保留默认提示
    }
    throw new Error(message)
  }
  return (await res.json()) as T
}

export const api = {
  login: (openId: string, nickname?: string) =>
    request<User>('/users/login', {
      method: 'POST',
      body: JSON.stringify({ open_id: openId, nickname: nickname || null, source: 'APP' }),
    }),

  createConversation: (userId: number, title?: string) =>
    request<{ id: number; user_id: number; title: string | null }>('/conversations', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, title: title || null }),
    }),

  listConversations: (userId: number) =>
    request<ConversationSummary[]>(`/conversations?user_id=${userId}`),

  conversationDetail: (conversationId: number) =>
    request<ConversationDetail>(`/conversations/${conversationId}`),

  sendMessage: (conversationId: number, content: string, startDate?: string | null) =>
    request<ChatResult>(`/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, start_date: startDate || null }),
    }),

  getTrip: (tripId: number) => request<Trip>(`/trips/${tripId}`),

  versions: (tripId: number) => request<VersionInfo[]>(`/trips/${tripId}/versions`),

  versionDetail: (tripId: number, versionId: number) =>
    request<Trip>(`/trips/${tripId}/versions/${versionId}`),

  compareVersions: (tripId: number, base: number, target: number) =>
    request<VersionCompare>(`/trips/${tripId}/versions/compare?base=${base}&target=${target}`),

  activateVersion: (tripId: number, versionId: number) =>
    request<Trip>(`/trips/${tripId}/versions/${versionId}/activate`, { method: 'POST' }),

  updateItem: (
    tripId: number,
    itemId: number,
    payload: { start_time?: string; end_time?: string; period?: string; note?: string },
  ) =>
    request<Trip>(`/trips/${tripId}/items/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteItem: (tripId: number, itemId: number) =>
    request<Trip>(`/trips/${tripId}/items/${itemId}`, { method: 'DELETE' }),

  moveItem: (tripId: number, itemId: number, direction: 'up' | 'down') =>
    request<Trip>(`/trips/${tripId}/items/${itemId}/move`, {
      method: 'POST',
      body: JSON.stringify({ direction }),
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
      body: JSON.stringify(payload),
    }),

  replaceHotel: (tripId: number, lodgingId: number, hotelId: number) =>
    request<Trip>(`/trips/${tripId}/lodgings/${lodgingId}/replace`, {
      method: 'POST',
      body: JSON.stringify({ hotel_id: hotelId }),
    }),

  replan: (tripId: number) =>
    request<Trip>(`/trips/${tripId}/replan`, { method: 'POST' }),

  createExport: (tripId: number, format: 'PDF' | 'LONG_IMAGE' | 'WECHAT_ARTICLE') =>
    request<ExportRecord>(`/trips/${tripId}/exports`, {
      method: 'POST',
      body: JSON.stringify({ format }),
    }),

  listExports: (tripId: number) => request<ExportRecord[]>(`/trips/${tripId}/exports`),

  styles: () => request<StyleOption[]>('/meta/styles'),

  cities: () => request<string[]>('/resources/cities'),

  pois: (city?: string, keyword?: string) => {
    const params = new URLSearchParams()
    if (city) params.set('city', city)
    if (keyword) params.set('keyword', keyword)
    const qs = params.toString()
    return request<PoiOption[]>(`/resources/pois${qs ? `?${qs}` : ''}`)
  },
}

export async function streamMessage(
  conversationId: number,
  content: string,
  startDate: string | null,
  onEvent: StreamHandler,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/conversations/${conversationId}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
