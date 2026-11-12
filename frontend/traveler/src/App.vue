<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import ChatPanel from './components/ChatPanel.vue'
import TripPanel from './components/TripPanel.vue'
import {
  api,
  API_BASE,
  resolveFileUrl,
  streamMessage,
  type AuthSession,
  type CaptchaResult,
} from './api/client'
import { clearToken, getToken } from './api/http'
import { debounce } from './utils/debounce'
import type {
  ConversationDetail,
  ConversationSummary,
  ExportRecord,
  Message,
  SlotInfo,
  ToolCallInfo,
  Trip,
  User,
  VersionCompare,
  VersionInfo,
} from './api/types'
import { formatDateTime } from './utils/format'

const STORAGE_KEY = 'traveler.open_id'
const NICKNAME_KEY = 'traveler.nickname'

const booting = ref(true)
const loggingIn = ref(false)
const openIdInput = ref('demo-traveler-001')
const nicknameInput = ref('旅行者')

type AuthTab = 'login' | 'register' | 'forgot'
const authTab = ref<AuthTab>('login')
const captcha = ref<CaptchaResult | null>(null)
const captchaLoading = ref(false)
const loginForm = reactive({ username: 'traveler', password: '', code: '' })
const registerForm = reactive({ username: '', password: '', nickname: '', email: '', phone: '', code: '' })
const forgotForm = reactive({ account: '', code: '', resetToken: '', newPassword: '' })

const user = ref<User | null>(null)
const conversations = ref<ConversationSummary[]>([])
const activeId = ref<number | null>(null)

const messages = ref<Message[]>([])
const slots = ref<Record<string, SlotInfo>>({})
const missingSlots = ref<string[]>([])

const trip = ref<Trip | null>(null)
const versions = ref<VersionInfo[]>([])
const exportRecords = ref<ExportRecord[]>([])
const compareResult = ref<VersionCompare | null>(null)

const streaming = ref(false)
const busy = ref(false)
const draft = ref('')
const errorMsg = ref('')
const toast = ref('')
const toolCalls = ref<ToolCallInfo[]>([])
const degraded = ref<string[]>([])

const loggedIn = computed(() => Boolean(user.value))
const conversationTitle = computed(
  () => conversations.value.find((item) => item.id === activeId.value)?.title || '新的旅行规划',
)

const intentLabels: Record<string, string> = {
  NEW_PLAN: '新行程',
  ADJUST: '调整行程',
  CONSULT: '旅行咨询',
  BLOCKED: '已拦截',
}

function showToast(message: string) {
  toast.value = message
  window.setTimeout(() => {
    if (toast.value === message) toast.value = ''
  }, 3600)
}

async function afterLogin(nextUser: User) {
  user.value = nextUser
  localStorage.setItem(STORAGE_KEY, nextUser.open_id)
  if (nextUser.nickname) localStorage.setItem(NICKNAME_KEY, nextUser.nickname)
  await loadConversations()
  if (conversations.value.length) {
    await openConversation(conversations.value[0].id)
  }
}

async function refreshCaptcha() {
  if (captchaLoading.value) return
  captchaLoading.value = true
  try {
    captcha.value = await api.captcha()
  } catch (err) {
    showToast(err instanceof Error ? err.message : '验证码加载失败')
  } finally {
    captchaLoading.value = false
  }
}

function switchTab(tab: AuthTab) {
  authTab.value = tab
  forgotForm.resetToken = ''
  if (!captcha.value) void refreshCaptcha()
}

async function submitPasswordLogin() {
  const cap = captcha.value
  if (!loginForm.username.trim() || !loginForm.password) {
    showToast('请输入账号与密码')
    return
  }
  if (!cap || !loginForm.code.trim()) {
    showToast('请输入图形验证码')
    return
  }
  loggingIn.value = true
  try {
    const session: AuthSession = await api.passwordLogin({
      username: loginForm.username.trim(),
      password: loginForm.password,
      captcha_id: cap.captcha_id,
      captcha_code: loginForm.code.trim(),
    })
    await afterLogin(session.user)
    showToast(`欢迎回来，${session.user.nickname || session.user.username}`)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '登录失败')
    loginForm.code = ''
    await refreshCaptcha()
  } finally {
    loggingIn.value = false
  }
}

async function submitRegister() {
  const cap = captcha.value
  if (!registerForm.username.trim() || !registerForm.password) {
    showToast('请填写用户名与密码')
    return
  }
  if (!cap || !registerForm.code.trim()) {
    showToast('请输入图形验证码')
    return
  }
  loggingIn.value = true
  try {
    const session: AuthSession = await api.register({
      username: registerForm.username.trim(),
      password: registerForm.password,
      nickname: registerForm.nickname.trim() || null,
      email: registerForm.email.trim() || null,
      phone: registerForm.phone.trim() || null,
      captcha_id: cap.captcha_id,
      captcha_code: registerForm.code.trim(),
    })
    await afterLogin(session.user)
    showToast('注册成功，已自动登录')
  } catch (err) {
    showToast(err instanceof Error ? err.message : '注册失败')
    registerForm.code = ''
    await refreshCaptcha()
  } finally {
    loggingIn.value = false
  }
}

async function submitForgot() {
  const cap = captcha.value
  if (!forgotForm.account.trim()) {
    showToast('请输入用户名或邮箱')
    return
  }
  if (!cap || !forgotForm.code.trim()) {
    showToast('请输入图形验证码')
    return
  }
  loggingIn.value = true
  try {
    const result = await api.forgotPassword(
      forgotForm.account.trim(),
      cap.captcha_id,
      forgotForm.code.trim(),
    )
    if (result.reset_token) {
      forgotForm.resetToken = result.reset_token
      showToast('验证通过，请设置新密码')
    } else {
      showToast(result.message)
    }
  } catch (err) {
    showToast(err instanceof Error ? err.message : '找回密码失败')
    forgotForm.code = ''
    await refreshCaptcha()
  } finally {
    loggingIn.value = false
  }
}

async function submitReset() {
  if (!forgotForm.newPassword) {
    showToast('请输入新密码')
    return
  }
  loggingIn.value = true
  try {
    const result = await api.resetPassword(forgotForm.resetToken, forgotForm.newPassword)
    showToast(result.message)
    forgotForm.resetToken = ''
    forgotForm.newPassword = ''
    forgotForm.code = ''
    authTab.value = 'login'
    loginForm.password = ''
    await refreshCaptcha()
  } catch (err) {
    showToast(err instanceof Error ? err.message : '重置失败')
  } finally {
    loggingIn.value = false
  }
}

async function doLogin() {
  const openId = openIdInput.value.trim()
  if (!openId || loggingIn.value) return
  loggingIn.value = true
  try {
    const logged = await api.login(openId, nicknameInput.value.trim() || undefined)
    await afterLogin(logged)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '登录失败')
  } finally {
    loggingIn.value = false
  }
}

const debouncedLogin = debounce(() => {
  void doLogin()
}, 400)

function submitLogin() {
  debouncedLogin()
}

async function logout() {
  try {
    await api.logout()
  } catch {
    // 会话可能已过期，本地清理仍需执行
  }
  localStorage.removeItem(STORAGE_KEY)
  localStorage.removeItem(NICKNAME_KEY)
  clearToken()
  user.value = null
  conversations.value = []
  activeId.value = null
  messages.value = []
  slots.value = {}
  missingSlots.value = []
  trip.value = null
  versions.value = []
  exportRecords.value = []
  compareResult.value = null
  errorMsg.value = ''
}

async function loadConversations() {
  if (!user.value) return
  try {
    conversations.value = await api.listConversations(user.value.id)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '会话列表加载失败')
  }
}

async function newConversation() {
  if (!user.value || streaming.value) return
  try {
    const created = await api.createConversation(user.value.id)
    await loadConversations()
    activeId.value = created.id
    messages.value = []
    slots.value = {}
    missingSlots.value = []
    trip.value = null
    versions.value = []
    exportRecords.value = []
    compareResult.value = null
    errorMsg.value = ''
  } catch (err) {
    showToast(err instanceof Error ? err.message : '新建会话失败')
  }
}

async function openConversation(conversationId: number) {
  if (streaming.value) return
  activeId.value = conversationId
  errorMsg.value = ''
  compareResult.value = null
  try {
    const detail: ConversationDetail = await api.conversationDetail(conversationId)
    applyDetail(detail)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '会话加载失败')
  }
}

function applyDetail(detail: ConversationDetail) {
  messages.value = detail.messages
  slots.value = detail.slots
  missingSlots.value = detail.missing_slots
  trip.value = detail.trip
  if (detail.trip) {
    void loadTripAux(detail.trip.id)
  } else {
    versions.value = []
    exportRecords.value = []
  }
}

async function loadTripAux(tripId: number) {
  try {
    const [versionRows, exportRows] = await Promise.all([
      api.versions(tripId),
      api.listExports(tripId),
    ])
    versions.value = versionRows
    exportRecords.value = exportRows
  } catch (err) {
    showToast(err instanceof Error ? err.message : '版本信息加载失败')
  }
}

async function refreshConversation() {
  if (!activeId.value) return
  try {
    const detail = await api.conversationDetail(activeId.value)
    applyDetail(detail)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '会话刷新失败')
  }
}

async function sendMessage(text: string) {
  const content = text.trim()
  if (!content || streaming.value || !user.value) return
  errorMsg.value = ''
  draft.value = ''
  toolCalls.value = []
  degraded.value = []

  let conversationId = activeId.value
  if (!conversationId) {
    try {
      const created = await api.createConversation(user.value.id)
      conversationId = created.id
      activeId.value = created.id
      await loadConversations()
    } catch (err) {
      showToast(err instanceof Error ? err.message : '新建会话失败')
      return
    }
  }

  messages.value.push({
    id: -Date.now(),
    seq: messages.value.length + 1,
    role: 'USER',
    content,
    content_type: 'TEXT',
    intent: null,
    stream_flag: 0,
    created_at: new Date().toISOString(),
  })

  streaming.value = true
  try {
    await streamMessage(conversationId, content, null, (event, data) => {
      if (event === 'slots') {
        missingSlots.value = (data.missing_slots as string[]) || []
      } else if (event === 'tool') {
        toolCalls.value.push(data as unknown as ToolCallInfo)
      } else if (event === 'degrade') {
        degraded.value = (data.tools as string[]) || []
      } else if (event === 'chunk') {
        draft.value += (data.content as string) || ''
      } else if (event === 'done') {
        const nextTrip = data.trip as Trip | null
        if (nextTrip) trip.value = nextTrip
      } else if (event === 'error') {
        errorMsg.value = (data.message as string) || '行程生成失败'
      }
    })
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '流式请求失败'
  } finally {
    streaming.value = false
    draft.value = ''
    await refreshConversation()
    await loadConversations()
  }
}

function applyTrip(next: Trip) {
  trip.value = next
  void loadTripAux(next.id)
}

async function runTripAction(action: () => Promise<Trip>, successMessage?: string) {
  if (busy.value || !trip.value) return
  busy.value = true
  try {
    const next = await action()
    applyTrip(next)
    if (successMessage) showToast(successMessage)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '操作失败')
  } finally {
    busy.value = false
  }
}

function updateItem(itemId: number, payload: { start_time: string; end_time: string }) {
  if (!trip.value) return
  void runTripAction(() => api.updateItem(trip.value!.id, itemId, payload), '时段已更新')
}

function deleteItem(itemId: number) {
  if (!trip.value) return
  void runTripAction(() => api.deleteItem(trip.value!.id, itemId), '条目已删除')
}

function moveItem(itemId: number, direction: 'up' | 'down') {
  if (!trip.value) return
  void runTripAction(() => api.moveItem(trip.value!.id, itemId, direction))
}

function addItem(payload: {
  day_index: number
  ref_name: string
  start_time: string
  end_time: string
}) {
  if (!trip.value) return
  void runTripAction(
    () =>
      api.addItem(trip.value!.id, {
        day_index: payload.day_index,
        item_type: 'FREE',
        ref_name: payload.ref_name,
        start_time: payload.start_time,
        end_time: payload.end_time,
      }),
    '已添加条目',
  )
}

function replan() {
  if (!trip.value) return
  void runTripAction(() => api.replan(trip.value!.id), 'AI 已重新排布')
}

async function compareVersions(base: number, target: number) {
  if (!trip.value) return
  try {
    compareResult.value = await api.compareVersions(trip.value.id, base, target)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '版本对比失败')
  }
}

function activateVersion(versionId: number) {
  if (!trip.value) return
  void runTripAction(() => api.activateVersion(trip.value!.id, versionId), '已切换版本')
}

async function exportTrip(format: 'PDF' | 'LONG_IMAGE' | 'WECHAT_ARTICLE') {
  if (!trip.value || busy.value) return
  busy.value = true
  try {
    const record = await api.createExport(trip.value.id, format)
    if (record.status === 2 && record.file_url) {
      window.open(resolveFileUrl(record.file_url), '_blank')
      showToast('导出完成')
    } else {
      showToast(record.fail_reason || '导出失败')
    }
    await loadTripAux(trip.value.id)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '导出失败')
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  const savedOpenId = localStorage.getItem(STORAGE_KEY)
  if (savedOpenId) {
    openIdInput.value = savedOpenId
    nicknameInput.value = localStorage.getItem(NICKNAME_KEY) || '旅行者'
  }
  // 有令牌则向服务端校验会话（Redis 中的凭证可能已被登出或过期）
  if (getToken()) {
    try {
      const session = await api.me()
      await afterLogin(session.user)
    } catch {
      clearToken()
    }
  }
  booting.value = false
  if (!user.value) await refreshCaptcha()
})
</script>

<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <div v-if="booting" class="splash">
      <div class="splash-logo" />
      <p class="muted">正在进入旅行规划空间…</p>
    </div>

    <template v-else-if="!loggedIn">
      <div class="login-page">
        <div class="login-shell">
          <aside class="login-aside">
            <div class="aside-brand">
              <div class="splash-logo" />
              <span>旅行规划智能体</span>
            </div>
            <div class="aside-copy">
              <p class="aside-eyebrow">AI 行程规划</p>
              <h2>把一句话，<br />变成一份能出发的行程</h2>
              <p class="aside-sub">实时查天气、交通与住宿，自动核算预算，行程随时可改。</p>
            </div>
            <ul class="aside-points">
              <li>实时天气 / 交通 / 酒店数据</li>
              <li>预算自动核算与行程导出</li>
              <li>多版本对比与一键回滚</li>
            </ul>
            <div class="aside-route" aria-hidden="true">
              <span class="route-dot" />
              <span class="route-line" />
              <span class="route-dot" />
              <span class="route-line" />
              <span class="route-dot end" />
            </div>
          </aside>

          <div class="login-card">
            <div class="brand-block">
              <div class="splash-logo" />
              <h1>旅行规划智能体</h1>
              <p class="muted">一句话生成完整行程 · 实时查 · 自动算 · 随时改</p>
            </div>

          <div class="auth-tabs">
            <button
              type="button"
              class="auth-tab"
              :class="{ active: authTab === 'login' }"
              @click="switchTab('login')"
            >
              账号登录
            </button>
            <button
              type="button"
              class="auth-tab"
              :class="{ active: authTab === 'register' }"
              @click="switchTab('register')"
            >
              注册账号
            </button>
            <button
              type="button"
              class="auth-tab"
              :class="{ active: authTab === 'forgot' }"
              @click="switchTab('forgot')"
            >
              找回密码
            </button>
          </div>

          <form v-if="authTab === 'login'" class="login-form" @submit.prevent="submitPasswordLogin">
            <label>
              账号
              <input v-model="loginForm.username" name="username" type="text" autocomplete="username" spellcheck="false" placeholder="用户名，如 traveler" />
            </label>
            <label>
              密码
              <input v-model="loginForm.password" name="password" type="password" autocomplete="current-password" placeholder="请输入密码" />
            </label>
            <label>
              图形验证码
              <div class="captcha-row">
                <input v-model="loginForm.code" name="captcha_code" type="text" maxlength="8" autocomplete="off" spellcheck="false" placeholder="输入右侧字符" />
                <button type="button" class="captcha-img" aria-label="刷新图形验证码" title="点击刷新" @click="refreshCaptcha">
                  <img v-if="captcha" :src="captcha.image" alt="图形验证码" width="120" height="42" />
                  <span v-else class="captcha-loading">{{ captchaLoading ? '加载中…' : '点击获取' }}</span>
                </button>
              </div>
            </label>
            <button type="submit" class="login-btn" :disabled="loggingIn">
              {{ loggingIn ? '登录中…' : '登录并进入规划空间' }}
            </button>
          </form>

          <form v-else-if="authTab === 'register'" class="login-form" @submit.prevent="submitRegister">
            <label>
              用户名
              <input v-model="registerForm.username" name="username" type="text" autocomplete="username" spellcheck="false" placeholder="3-32 位字母、数字或下划线" />
            </label>
            <label>
              密码
              <input v-model="registerForm.password" name="password" type="password" autocomplete="new-password" placeholder="至少 8 位，需含字母与数字" />
            </label>
            <div class="form-grid">
              <label>
                昵称（可选）
                <input v-model="registerForm.nickname" name="nickname" type="text" autocomplete="nickname" placeholder="旅行者" />
              </label>
              <label>
                手机号（可选）
                <input v-model="registerForm.phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="用于找回密码" />
              </label>
            </div>
            <label>
              邮箱（可选）
              <input v-model="registerForm.email" name="email" type="email" autocomplete="email" spellcheck="false" placeholder="用于找回密码" />
            </label>
            <label>
              图形验证码
              <div class="captcha-row">
                <input v-model="registerForm.code" name="captcha_code" type="text" maxlength="8" autocomplete="off" spellcheck="false" placeholder="输入右侧字符" />
                <button type="button" class="captcha-img" aria-label="刷新图形验证码" title="点击刷新" @click="refreshCaptcha">
                  <img v-if="captcha" :src="captcha.image" alt="图形验证码" width="120" height="42" />
                  <span v-else class="captcha-loading">{{ captchaLoading ? '加载中…' : '点击获取' }}</span>
                </button>
              </div>
            </label>
            <button type="submit" class="login-btn" :disabled="loggingIn">
              {{ loggingIn ? '注册中…' : '注册并登录' }}
            </button>
          </form>

          <form v-else class="login-form" @submit.prevent="forgotForm.resetToken ? submitReset() : submitForgot()">
            <template v-if="!forgotForm.resetToken">
              <label>
                用户名或邮箱
                <input v-model="forgotForm.account" name="account" type="text" autocomplete="username" spellcheck="false" placeholder="注册时使用的用户名或邮箱" />
              </label>
              <label>
                图形验证码
                <div class="captcha-row">
                  <input v-model="forgotForm.code" name="captcha_code" type="text" maxlength="8" autocomplete="off" spellcheck="false" placeholder="输入右侧字符" />
                  <button type="button" class="captcha-img" aria-label="刷新图形验证码" title="点击刷新" @click="refreshCaptcha">
                    <img v-if="captcha" :src="captcha.image" alt="图形验证码" width="120" height="42" />
                    <span v-else class="captcha-loading">{{ captchaLoading ? '加载中…' : '点击获取' }}</span>
                  </button>
                </div>
              </label>
              <button type="submit" class="login-btn" :disabled="loggingIn">
                {{ loggingIn ? '校验中…' : '获取重置凭证' }}
              </button>
            </template>
            <template v-else>
              <label>
                新密码
                <input v-model="forgotForm.newPassword" name="new_password" type="password" autocomplete="new-password" placeholder="至少 8 位，需含字母与数字" />
              </label>
              <button type="submit" class="login-btn" :disabled="loggingIn">
                {{ loggingIn ? '提交中…' : '确认重置密码' }}
              </button>
              <p class="auth-note muted">重置凭证 10 分钟内有效，且仅可使用一次。</p>
            </template>
          </form>

          <details class="demo-login">
            <summary>其他登录方式：OpenID 演示登录</summary>
            <form class="login-form" @submit.prevent="submitLogin">
              <label>
                账号标识
                <input v-model="openIdInput" name="open_id" type="text" spellcheck="false" placeholder="任意唯一标识，如 demo-traveler-001" />
              </label>
              <label>
                昵称（可选）
                <input v-model="nicknameInput" name="nickname" type="text" autocomplete="nickname" placeholder="旅行者" />
              </label>
              <button type="submit" class="login-btn ghost" :disabled="loggingIn || !openIdInput.trim()">
                {{ loggingIn ? '登录中…' : '以 OpenID 进入' }}
              </button>
            </form>
          </details>

          <p class="login-hint muted">
            登录凭证保存在当前标签页会话中，关闭即失效；接口地址
            <code>{{ API_BASE }}</code>
          </p>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <aside class="sidebar">
        <div class="sidebar-brand">
          <div class="brand-dot" />
          <div class="brand-text">
            <span class="brand-name">旅行规划智能体</span>
            <span class="brand-sub">AI TRAVEL PLANNER</span>
          </div>
        </div>

        <button type="button" class="new-chat-btn" :disabled="streaming" @click="newConversation">
          + 新的规划
        </button>

        <nav class="conversation-list">
          <button
            v-for="item in conversations"
            :key="item.id"
            type="button"
            class="conversation-item"
            :class="{ active: item.id === activeId }"
            @click="openConversation(item.id)"
          >
            <span class="conversation-title">{{ item.title || '未命名会话' }}</span>
            <span class="conversation-meta">
              <span>{{ intentLabels[item.last_intent || ''] || '规划中' }}</span>
              <span class="conversation-count">{{ item.message_count || 0 }} 条</span>
            </span>
            <span v-if="item.last_message_at" class="conversation-time">
              {{ formatDateTime(item.last_message_at) }}
            </span>
          </button>
          <p v-if="!conversations.length" class="sidebar-empty muted">
            还没有会话，直接输入旅行需求即可开始。
          </p>
        </nav>

        <div class="sidebar-footer">
          <div class="user-chip">
            <span class="user-avatar">{{ (user?.nickname || '旅').slice(0, 1) }}</span>
            <span class="user-name">{{ user?.nickname || '旅行者' }}</span>
          </div>
          <button type="button" class="logout-btn" @click="logout">退出</button>
        </div>
      </aside>

      <main id="main-content" class="workspace">
        <div class="workspace-head">
          <span class="workspace-title">{{ conversationTitle }}</span>
          <span class="workspace-sub muted">
            {{ activeId ? `会话 #${activeId}` : '新会话将在首次提问时创建' }}
          </span>
        </div>
        <div class="workspace-body">
          <ChatPanel
            :messages="messages"
            :draft="draft"
            :streaming="streaming"
            :slots="slots"
            :missing-slots="missingSlots"
            :tool-calls="toolCalls"
            :degraded="degraded"
            :error="errorMsg"
            :disabled="busy"
            @send="sendMessage"
          />
          <TripPanel
            :trip="trip"
            :versions="versions"
            :exports="exportRecords"
            :compare="compareResult"
            :busy="busy || streaming"
            @replan="replan"
            @export="exportTrip"
            @activate="activateVersion"
            @compare="compareVersions"
            @update-item="updateItem"
            @delete-item="deleteItem"
            @move-item="moveItem"
            @add-item="addItem"
          />
        </div>
      </main>
    </template>

    <transition name="toast">
      <div v-if="toast" class="toast" role="status" aria-live="polite">{{ toast }}</div>
    </transition>
  </div>
</template>

<style scoped>
.app-shell {
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: var(--bg);
}

.skip-link {
  position: absolute;
  left: 12px;
  top: -48px;
  z-index: 100;
  padding: 8px 14px;
  border-radius: 8px;
  background: var(--ink);
  color: #fff;
  font-size: 13px;
  text-decoration: none;
  transition: top 0.15s ease;
}

.skip-link:focus-visible {
  top: 12px;
}

.splash {
  margin: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.splash-logo {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: var(--accent);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.18),
    0 10px 24px rgba(15, 118, 110, 0.24);
}

/* 罗盘缺口环：以出行方向为意象的品牌记号，替代装饰性渐变色块 */
.splash-logo::after {
  content: '';
  position: absolute;
  inset: 13px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.82);
  border-right-color: transparent;
  transform: rotate(-45deg);
}

.login-page {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  padding: 28px;
  overflow: auto;
}

.login-shell {
  width: min(980px, 100%);
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 24px;
  box-shadow: 0 30px 70px -42px rgba(15, 23, 42, 0.5);
  overflow: hidden;
}

.login-aside {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 26px;
  padding: 36px 34px 30px;
  background: linear-gradient(168deg, #0b4a44, #08312d 62%, #072522);
  color: #e8f6f3;
}

.aside-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
}

.aside-brand .splash-logo {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.12);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.24);
}

.aside-brand .splash-logo::after {
  inset: 9px;
  border-width: 1.5px;
  border-color: rgba(255, 255, 255, 0.9);
  border-right-color: transparent;
}

.aside-copy {
  margin-top: auto;
}

.aside-eyebrow {
  margin: 0 0 10px;
  font-size: 11.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #7fd8cd;
}

.aside-copy h2 {
  margin: 0;
  font-size: 29px;
  line-height: 1.34;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: #fff;
}

.aside-sub {
  margin: 14px 0 0;
  max-width: 34ch;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(232, 246, 243, 0.72);
}

.aside-points {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
  font-size: 12.5px;
  color: rgba(232, 246, 243, 0.82);
}

.aside-points li {
  display: flex;
  align-items: center;
  gap: 8px;
}

.aside-points li::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #5eead4;
  flex-shrink: 0;
}

.aside-route {
  display: flex;
  align-items: center;
  margin-top: 4px;
}

.route-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.42);
}

.route-dot.end {
  background: #5eead4;
  box-shadow: 0 0 0 4px rgba(94, 234, 212, 0.16);
}

.route-line {
  width: 34px;
  height: 1px;
  margin: 0 6px;
  background: rgba(255, 255, 255, 0.22);
}

.login-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 34px 36px;
}

.brand-block {
  display: none;
  text-align: center;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

@media (max-width: 900px) {
  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-aside {
    display: none;
  }

  .login-card {
    padding: 30px 26px;
  }

  .brand-block {
    display: flex;
  }
}

.brand-block .splash-logo {
  width: 48px;
  height: 48px;
  border-radius: 15px;
  margin-bottom: 4px;
}

.brand-block h1 {
  margin: 0;
  font-size: 22px;
  color: var(--ink);
}

.brand-block p {
  margin: 0;
  font-size: 13px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 26px;
}

.login-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12.5px;
  color: var(--text-muted);
}

.login-form input {
  font: inherit;
  font-size: 14px;
  color: var(--ink);
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--line-strong);
  background: #fff;
}

.login-form input:focus {
  outline: 2px solid var(--accent-ring);
  border-color: var(--accent);
}

.login-btn {
  margin-top: 6px;
  padding: 11px 16px;
  border: none;
  border-radius: 10px;
  background: var(--accent);
  color: #fff;
  font: inherit;
  font-size: 14px;
  cursor: pointer;
}

.login-btn:hover:not(:disabled) {
  background: var(--accent-strong);
}

.login-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.login-hint {
  margin: 18px 0 0;
  font-size: 11.5px;
  line-height: 1.6;
  text-align: center;
}

.login-hint code {
  background: var(--panel-alt);
  padding: 1px 5px;
  border-radius: 4px;
}

.auth-tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  margin-top: 22px;
  padding: 4px;
  background: var(--panel-alt);
  border-radius: 12px;
}

.auth-tab {
  padding: 8px 6px;
  border: none;
  border-radius: 9px;
  background: transparent;
  font: inherit;
  font-size: 12.5px;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.auth-tab:hover {
  color: var(--ink);
}

.auth-tab.active {
  background: #fff;
  color: var(--accent-strong);
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
}

.captcha-row {
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.captcha-row input {
  flex: 1;
  min-width: 0;
}

.captcha-img {
  width: 120px;
  height: 42px;
  flex-shrink: 0;
  padding: 0;
  border: 1px solid var(--line-strong);
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  cursor: pointer;
}

.captcha-img img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.captcha-loading {
  font-size: 11.5px;
  color: var(--text-muted);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.auth-note {
  margin: 2px 0 0;
  font-size: 11.5px;
  text-align: center;
}

.login-btn.ghost {
  background: #fff;
  color: var(--accent-strong);
  border: 1px solid var(--line-strong);
}

.login-btn.ghost:hover:not(:disabled) {
  background: var(--accent-soft);
}

.demo-login {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dashed var(--line);
}

.demo-login summary {
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  list-style: none;
  text-align: center;
}

.demo-login summary::-webkit-details-marker {
  display: none;
}

.demo-login summary:hover {
  color: var(--accent-strong);
}

.demo-login .login-form {
  margin-top: 14px;
}

@media (max-width: 520px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}

.sidebar {
  width: 264px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--panel);
  border-right: 1px solid var(--line);
  padding: 18px 14px 14px;
  gap: 14px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 6px 4px;
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.brand-name {
  font-size: 14px;
  font-weight: 650;
  color: var(--ink);
  line-height: 1.2;
}

.brand-sub {
  font-size: 9.5px;
  letter-spacing: 0.14em;
  color: var(--text-muted);
}

.brand-dot {
  position: relative;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: var(--accent);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.16);
  flex-shrink: 0;
}

.brand-dot::after {
  content: '';
  position: absolute;
  inset: 7px;
  border-radius: 50%;
  border: 1.5px solid rgba(255, 255, 255, 0.82);
  border-right-color: transparent;
  transform: rotate(-45deg);
}

.new-chat-btn {
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  padding: 10px 12px;
  border-radius: 12px;
  border: none;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  transition: background 0.15s, transform 0.15s;
}

.new-chat-btn:hover:not(:disabled) {
  background: var(--accent-strong);
  transform: translateY(-1px);
}

.new-chat-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.conversation-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  font: inherit;
  color: var(--text);
  transition: background 0.15s;
}

.conversation-item:hover {
  background: var(--panel-alt);
}

.conversation-item.active {
  background: var(--accent-soft);
  border-color: transparent;
  box-shadow: inset 3px 0 0 var(--accent);
}

.conversation-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conversation-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
}

.conversation-count {
  color: var(--text-muted);
}

.conversation-time {
  font-size: 10.5px;
  color: #9aa3ad;
}

.sidebar-empty {
  font-size: 12px;
  padding: 10px;
  line-height: 1.6;
}

.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-top: 1px solid var(--line);
  padding-top: 10px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent-strong);
  display: grid;
  place-items: center;
  font-size: 12px;
  flex-shrink: 0;
}

.user-name {
  font-size: 12.5px;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-btn {
  border: none;
  background: none;
  font: inherit;
  font-size: 11.5px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px 4px;
}

.logout-btn:hover {
  color: #b91c1c;
}

.workspace {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.workspace-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 26px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(8px);
  position: sticky;
  top: 0;
  z-index: 5;
}

.workspace-title {
  font-size: 15px;
  font-weight: 650;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-sub {
  font-size: 11px;
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--panel-alt);
  border: 1px solid var(--line);
  color: var(--text-muted);
  white-space: nowrap;
}

.workspace-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(360px, 0.9fr) minmax(420px, 1.1fr);
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  background: rgba(15, 23, 42, 0.9);
  color: #fff;
  font-size: 13px;
  padding: 9px 16px;
  border-radius: 999px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.28);
  z-index: 50;
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(6px);
}

@media (max-width: 1024px) {
  .sidebar {
    width: 200px;
  }

  .workspace-body {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(280px, 42%) 1fr;
  }

  .workspace-head {
    padding: 10px 16px;
  }
}
</style>
