<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ChatPanel from './components/ChatPanel.vue'
import FileTransferPanel from './components/FileTransferPanel.vue'
import TripPanel from './components/TripPanel.vue'
import { api, API_BASE, resolveFileUrl, streamMessage } from './api/client'
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
const showFiles = ref(false)

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

async function doLogin() {
  const openId = openIdInput.value.trim()
  if (!openId || loggingIn.value) return
  loggingIn.value = true
  try {
    const logged = await api.login(openId, nicknameInput.value.trim() || undefined)
    user.value = logged
    localStorage.setItem(STORAGE_KEY, logged.open_id)
    if (logged.nickname) localStorage.setItem(NICKNAME_KEY, logged.nickname)
    await loadConversations()
    if (conversations.value.length) {
      await openConversation(conversations.value[0].id)
    }
  } catch (err) {
    showToast(err instanceof Error ? err.message : '登录失败')
  } finally {
    loggingIn.value = false
  }
}

function logout() {
  localStorage.removeItem(STORAGE_KEY)
  localStorage.removeItem(NICKNAME_KEY)
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
    await doLogin()
  }
  booting.value = false
})
</script>

<template>
  <div class="app-shell">
    <div v-if="booting" class="splash">
      <div class="splash-logo" />
      <p class="muted">正在进入旅行规划空间…</p>
    </div>

    <template v-else-if="!loggedIn">
      <div class="login-page">
        <div class="login-card">
          <div class="brand-block">
            <div class="splash-logo" />
            <h1>旅行规划智能体</h1>
            <p class="muted">一句话生成完整行程 · 实时查 · 自动算 · 随时改</p>
          </div>
          <form class="login-form" @submit.prevent="doLogin">
            <label>
              账号标识
              <input v-model="openIdInput" type="text" placeholder="任意唯一标识，如 demo-traveler-001" />
            </label>
            <label>
              昵称（可选）
              <input v-model="nicknameInput" type="text" placeholder="旅行者" />
            </label>
            <button type="submit" class="login-btn" :disabled="loggingIn || !openIdInput.trim()">
              {{ loggingIn ? '登录中…' : '进入规划空间' }}
            </button>
          </form>
          <p class="login-hint muted">
            当前为演示环境，登录信息仅保存在本地浏览器；接口地址
            <code>{{ API_BASE }}</code>
          </p>
        </div>
      </div>
    </template>

    <template v-else>
      <aside class="sidebar">
        <div class="sidebar-brand">
          <div class="brand-dot" />
          <span>旅行规划智能体</span>
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
          <div class="footer-actions">
            <button type="button" class="files-btn" @click="showFiles = true">文件空间</button>
            <button type="button" class="logout-btn" @click="logout">退出</button>
          </div>
        </div>
      </aside>

      <main class="workspace">
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

    <FileTransferPanel
      v-if="showFiles && user"
      :user-id="user.id"
      @close="showFiles = false"
    />

    <transition name="toast">
      <div v-if="toast" class="toast">{{ toast }}</div>
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

.splash {
  margin: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.splash-logo {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background:
    radial-gradient(circle at 30% 28%, #5eead4 0, transparent 55%),
    radial-gradient(circle at 72% 72%, #fcd34d 0, transparent 52%),
    #0f766e;
  box-shadow: 0 10px 24px rgba(15, 118, 110, 0.28);
}

.login-page {
  margin: auto;
  width: 100%;
  display: grid;
  place-items: center;
  padding: 24px;
}

.login-card {
  width: min(430px, 100%);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 32px;
  box-shadow: var(--shadow);
}

.brand-block {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
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

.sidebar {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--sidebar);
  border-right: 1px solid var(--line);
  padding: 16px 12px 12px;
  gap: 12px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  padding: 2px 8px;
}

.brand-dot {
  width: 22px;
  height: 22px;
  border-radius: 8px;
  background:
    radial-gradient(circle at 30% 28%, #5eead4 0, transparent 55%),
    radial-gradient(circle at 72% 72%, #fcd34d 0, transparent 52%),
    #0f766e;
}

.new-chat-btn {
  font: inherit;
  font-size: 13px;
  padding: 9px 12px;
  border-radius: 10px;
  border: 1px dashed var(--line-strong);
  background: #fff;
  color: var(--accent-strong);
  cursor: pointer;
}

.new-chat-btn:hover:not(:disabled) {
  border-color: var(--accent);
  background: var(--accent-soft);
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
  gap: 4px;
}

.conversation-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  text-align: left;
  padding: 9px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  font: inherit;
  color: var(--text);
}

.conversation-item:hover {
  background: #fff;
}

.conversation-item.active {
  background: #fff;
  border-color: var(--line-strong);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
}

.conversation-title {
  font-size: 13px;
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

.footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.files-btn {
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--ink);
  border-radius: 8px;
  padding: 4px 8px;
  font: inherit;
  font-size: 11.5px;
  cursor: pointer;
}

.files-btn:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}

.workspace {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.workspace-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 12px 22px;
  border-bottom: 1px solid var(--line);
  background: var(--panel);
}

.workspace-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}

.workspace-sub {
  font-size: 11.5px;
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
