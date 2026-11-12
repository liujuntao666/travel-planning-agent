import { reactive } from 'vue'

import { clearToken, getToken, request, setToken, setUnauthorizedHandler } from '../api/http'
import type { Captcha, LoginResult, MePayload } from '../api/types'

interface AuthState {
  me: MePayload | null
  loading: boolean
  booting: boolean
}

export const auth = reactive<AuthState>({ me: null, loading: false, booting: true })

setUnauthorizedHandler(() => {
  auth.me = null
})

export async function restoreSession(): Promise<void> {
  if (!getToken()) {
    auth.booting = false
    return
  }
  auth.loading = true
  try {
    auth.me = await request<MePayload>('/auth/me')
  } catch {
    auth.me = null
  } finally {
    auth.loading = false
    auth.booting = false
  }
}

export async function refreshMe(): Promise<void> {
  auth.me = await request<MePayload>('/auth/me')
}

export async function loginAccount(payload: {
  username: string
  password: string
  captcha_id: string
  captcha_code: string
}): Promise<LoginResult> {
  const data = await request<LoginResult>('/auth/login', { method: 'POST', data: payload })
  setToken(data.access_token)
  await refreshMe()
  return data
}

export async function registerAccount(payload: {
  username: string
  password: string
  nickname?: string | null
  email?: string | null
  phone?: string | null
  captcha_id: string
  captcha_code: string
}): Promise<void> {
  const data = await request<LoginResult>('/auth/register', { method: 'POST', data: payload })
  setToken(data.access_token)
  await refreshMe()
}

export async function logoutAccount(): Promise<void> {
  try {
    await request('/auth/logout', { method: 'POST' })
  } catch {
    // 会话已失效时直接清理本地状态
  } finally {
    clearToken()
    auth.me = null
  }
}

export function hasPermission(code: string): boolean {
  const me = auth.me
  if (!me) return false
  return me.is_admin || me.permissions.includes(code)
}

export function fetchCaptcha(): Promise<Captcha> {
  return request<Captcha>('/auth/captcha')
}
