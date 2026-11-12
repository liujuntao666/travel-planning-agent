const RAW_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || 'http://127.0.0.1:8001/api/v1'

export const API_BASE = RAW_BASE.replace(/\/+$/, '')

const TOKEN_KEY = 'admin.access_token'
const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export class ApiError extends Error {
  status: number
  code: string

  constructor(message: string, status: number, code = 'ERROR') {
    super(message)
    this.status = status
    this.code = code
  }
}

let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void) {
  unauthorizedHandler = handler
}

// 令牌保存在 sessionStorage：关闭标签页即失效，降低 XSS 持久化窃取风险
export function getToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string | null | undefined) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token)
  else sessionStorage.removeItem(TOKEN_KEY)
}

export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY)
}

export function newRequestId(): string {
  const cryptoObj = globalThis.crypto
  if (cryptoObj && 'randomUUID' in cryptoObj) return cryptoObj.randomUUID()
  return `req-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`
}

type QueryValue = string | number | boolean | null | undefined

export interface RequestOptions {
  method?: string
  data?: unknown
  params?: Record<string, QueryValue>
  headers?: Record<string, string>
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const query = new URLSearchParams()
  Object.entries(options.params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.append(key, String(value))
  })
  const url = `${API_BASE}${path}${query.toString() ? `?${query}` : ''}`
  const method = (options.method || 'GET').toUpperCase()
  const headers: Record<string, string> = { Accept: 'application/json', ...(options.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.data !== undefined) headers['Content-Type'] = 'application/json'
  if (MUTATING.has(method) && !headers['Idempotency-Key']) {
    headers['Idempotency-Key'] = newRequestId()
  }

  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: options.data !== undefined ? JSON.stringify(options.data) : undefined,
    })
  } catch {
    throw new ApiError('网络异常，请检查后端服务是否已启动', 0, 'NETWORK_ERROR')
  }

  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`
    let code = 'ERROR'
    try {
      const data = (await response.json()) as {
        message?: string
        code?: string
        errors?: Array<{ message?: string }>
      }
      if (data.message) message = data.message
      if (data.code) code = data.code
      const fieldError = data.errors?.[0]?.message
      if (fieldError && (!data.message || data.message === '参数校验失败')) message = fieldError
    } catch {
      // 非 JSON 错误响应
    }
    if (response.status === 401) {
      clearToken()
      unauthorizedHandler?.()
    }
    throw new ApiError(message, response.status, code)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
