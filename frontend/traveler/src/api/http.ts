import axios, { AxiosError, type AxiosRequestConfig } from 'axios'

const RAW_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || 'http://127.0.0.1:8001/api/v1'

export const API_BASE = RAW_BASE.replace(/\/+$/, '')
export const API_ORIGIN = API_BASE.replace(/\/api\/v1$/, '')

const TOKEN_KEY = 'traveler.token'
const MUTATING = new Set(['post', 'put', 'patch', 'delete'])

// 令牌仅存于当前标签页会话，关闭即失效，避免长期落盘被脚本读取
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

export function resolveFileUrl(url?: string | null): string {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  return `${API_ORIGIN}${url.startsWith('/') ? url : `/${url}`}`
}

export function errorMessage(error: unknown): string {
  const axiosError = error as AxiosError<{ message?: string; detail?: string; errors?: { message?: string }[] }>
  const data = axiosError?.response?.data
  const fieldError = data?.errors?.map((item) => item.message).filter(Boolean).join('；')
  if (fieldError && (!data?.message || data.message === '参数校验失败')) return fieldError
  if (data?.message) return data.message
  if (data?.detail) return data.detail
  if (axiosError?.code === 'ECONNABORTED') return '请求超时，请稍后重试'
  if (axiosError?.response?.status) return `请求失败（HTTP ${axiosError.response.status}）`
  return axiosError?.message || '网络异常，请检查服务是否启动'
}

export const http = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  const method = (config.method || 'get').toLowerCase()
  if (MUTATING.has(method) && !config.headers['Idempotency-Key']) {
    config.headers['Idempotency-Key'] = newRequestId()
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) clearToken()
    return Promise.reject(new Error(errorMessage(error)))
  },
)

export async function request<T>(path: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await http.request<T>({ url: path, ...config })
  return response.data
}
