<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { request } from '../api/http'
import {
  ChatClient,
  newClientId,
  type ChatMessage,
  type ChatStatus,
  type ChatThreadInfo,
} from '../api/chat'
import { timeText } from '../utils/format'
import type { User } from '../api/types'

const props = defineProps<{ user: User }>()

const open = ref(false)
const ready = ref(false)
const threadId = ref(0)
const messages = ref<ChatMessage[]>([])
const status = ref<ChatStatus>('offline')
const unread = ref(0)
const input = ref('')
const errorMsg = ref('')
const scroller = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)

let client: ChatClient | null = null
let errorTimer = 0

const quickQuestions = [
  '预算怎么分配更合理？',
  '帮我推荐离景区近的酒店',
  '行程节奏能再慢一点吗？',
]

const statusLabel = computed(() => {
  if (!ready.value) return '连接中'
  if (status.value === 'online') return '在线'
  if (status.value === 'connecting') return '连接中'
  return '已断开，重连中'
})

const connected = computed(() => status.value === 'online')

function keyOf(message: ChatMessage): string {
  return message.client_id ? `c:${message.client_id}` : `i:${message.id}`
}

function sortMessages(list: ChatMessage[]): ChatMessage[] {
  return [...list].sort((a, b) => {
    const sa = a.seq || Number.MAX_SAFE_INTEGER
    const sb = b.seq || Number.MAX_SAFE_INTEGER
    if (sa !== sb) return sa - sb
    return (a.created_at || '').localeCompare(b.created_at || '')
  })
}

function merge(incoming: ChatMessage[]) {
  const map = new Map<string, ChatMessage>()
  for (const message of messages.value) map.set(keyOf(message), message)
  for (const message of incoming) {
    const key = keyOf(message)
    const existing = map.get(key)
    if (existing) {
      existing.id = message.id
      existing.seq = message.seq
      existing.read_flag = message.read_flag
      existing.status = 'sent'
    } else {
      map.set(key, { ...message, status: 'sent' })
    }
  }
  messages.value = sortMessages([...map.values()])
  void scrollToBottom()
}

async function scrollToBottom() {
  await nextTick()
  const el = scroller.value
  if (el) el.scrollTop = el.scrollHeight
}

function showError(message: string) {
  errorMsg.value = message
  window.clearTimeout(errorTimer)
  errorTimer = window.setTimeout(() => {
    if (errorMsg.value === message) errorMsg.value = ''
  }, 4000)
}

function markRead() {
  if (!client || !threadId.value) return
  const maxSeq = messages.value
    .filter((message) => message.sender_role === 'ADVISOR' && message.seq > 0)
    .reduce((max, message) => Math.max(max, message.seq), 0)
  unread.value = 0
  if (!maxSeq) return
  client.read(maxSeq)
  void request(`/chat/threads/${threadId.value}/read`, {
    method: 'POST',
    data: { seq: maxSeq },
  }).catch(() => undefined)
}

function handleIncoming(message: ChatMessage) {
  merge([message])
  if (message.sender_role !== 'ADVISOR') return
  if (open.value) markRead()
  else unread.value += 1
}

function submit(text?: string) {
  const content = (text ?? input.value).trim()
  if (!content || !client) return
  const local: ChatMessage = {
    id: -Date.now(),
    seq: 0,
    sender_id: props.user.id,
    sender_role: 'USER',
    content,
    client_id: newClientId(),
    read_flag: 0,
    created_at: new Date().toISOString(),
    status: 'sending',
  }
  messages.value = sortMessages([...messages.value, local])
  client.send(local)
  input.value = ''
  errorMsg.value = ''
  void scrollToBottom()
  void nextTick(() => inputEl.value?.focus())
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}

function reconnect() {
  errorMsg.value = ''
  client?.connect()
}

async function init() {
  try {
    const info = await request<ChatThreadInfo>('/chat/thread')
    threadId.value = info.thread_id
    unread.value = info.unread
    client = new ChatClient({
      threadId: info.thread_id,
      onMessage: handleIncoming,
      onAck: (clientId, seq, id) => {
        const target = messages.value.find((message) => message.client_id === clientId)
        if (!target) return
        target.seq = seq
        target.id = id
        target.status = 'sent'
        messages.value = sortMessages(messages.value)
      },
      onFailed: (clientId) => {
        const target = messages.value.find((message) => message.client_id === clientId)
        if (target) target.status = 'failed'
      },
      onSync: (list) => merge(list),
      onRead: (seq) => {
        for (const message of messages.value) {
          if (message.sender_role === 'USER' && message.seq > 0 && message.seq <= seq) {
            message.read_flag = 1
          }
        }
      },
      onStatus: (next) => {
        status.value = next
      },
      onError: showError,
    })
    client.connect()
  } catch (err) {
    showError(err instanceof Error ? err.message : '聊天服务初始化失败')
  } finally {
    ready.value = true
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) {
    unread.value = 0
    markRead()
    void scrollToBottom()
    void nextTick(() => inputEl.value?.focus())
  }
}

function close() {
  open.value = false
}

function onWindowKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) close()
}

watch(open, (value) => {
  if (value) {
    unread.value = 0
    markRead()
    void scrollToBottom()
  }
})

onMounted(() => {
  void init()
  window.addEventListener('keydown', onWindowKeydown)
})

onBeforeUnmount(() => {
  window.clearTimeout(errorTimer)
  window.removeEventListener('keydown', onWindowKeydown)
  client?.close()
})
</script>

<template>
  <div class="chat-widget">
    <transition name="panel">
      <section v-if="open" class="chat-box" role="dialog" aria-label="旅行顾问实时聊天">
        <header class="chat-box-head">
          <div class="advisor-avatar">顾</div>
          <div class="advisor-meta">
            <strong>旅行顾问</strong>
            <span class="conn" :class="status">
              <i class="dot" />{{ statusLabel }}
            </span>
          </div>
          <button type="button" class="icon-btn" aria-label="收起聊天" @click="close">×</button>
        </header>

        <div ref="scroller" class="chat-box-body">
          <div class="notice">会话已加密传输，消息按序号可靠投递；断线后会自动补齐。</div>
          <div v-if="!messages.length" class="chat-empty">
            <p>你好，我是你的旅行顾问。行程、预算、住宿、交通都可以问我。</p>
            <div class="quick-list">
              <button
                v-for="question in quickQuestions"
                :key="question"
                type="button"
                class="quick-btn"
                @click="submit(question)"
              >
                {{ question }}
              </button>
            </div>
          </div>

          <div
            v-for="message in messages"
            :key="keyOf(message)"
            class="row"
            :class="message.sender_role === 'USER' ? 'mine' : 'theirs'"
          >
            <div class="bubble">
              <p class="content">{{ message.content }}</p>
              <span class="meta">
                {{ timeText(message.created_at?.slice(11)) }}
                <template v-if="message.sender_role === 'USER'">
                  · {{ message.status === 'failed' ? '发送失败' : message.status === 'sending' ? '发送中' : message.read_flag ? '已读' : '已送达' }}
                </template>
              </span>
            </div>
          </div>
        </div>

        <p v-if="errorMsg" class="chat-error">{{ errorMsg }}</p>

        <footer class="chat-box-foot">
          <div v-if="!connected" class="offline-bar">
            连接已断开
            <button type="button" class="retry-btn" @click="reconnect">重新连接</button>
          </div>
          <div class="composer">
            <textarea
              ref="inputEl"
              v-model="input"
              rows="1"
              placeholder="输入你想咨询的问题…"
              @keydown="onKeydown"
            />
            <button type="button" class="send" :disabled="!input.trim() || !connected" @click="submit()">
              发送
            </button>
          </div>
        </footer>
      </section>
    </transition>

    <button
      type="button"
      class="launcher"
      :class="{ active: open }"
      :aria-label="open ? '收起旅行顾问聊天' : '打开旅行顾问聊天'"
      @click="toggle"
    >
      <span class="launcher-avatar">
        <span class="launcher-icon">💬</span>
        <i class="presence" :class="status" />
      </span>
      <span class="launcher-text">
        <strong>旅行顾问</strong>
        <small>{{ statusLabel }}</small>
      </span>
      <span v-if="unread" class="badge">{{ unread > 99 ? '99+' : unread }}</span>
    </button>
  </div>
</template>

<style scoped>
.chat-widget {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 60;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}

.launcher {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 58px;
  padding: 0 20px 0 9px;
  border-radius: 999px;
  border: 1px solid var(--accent-strong);
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 14px 30px -12px var(--accent-ring), 0 4px 10px -6px rgba(15, 23, 42, 0.4);
  transition: transform 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
}

/* 首次出现时脉冲三次，吸引注意后自动停止，避免长期动效干扰阅读 */
.launcher::after {
  content: "";
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  pointer-events: none;
  animation: launcher-pulse 2.6s ease-out 3;
}

.launcher:hover {
  transform: translateY(-2px);
  background: var(--accent-strong);
  box-shadow: 0 20px 38px -14px var(--accent-ring), 0 8px 16px -10px rgba(15, 23, 42, 0.45);
}

.launcher:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
}

.launcher.active {
  background: var(--accent-strong);
}

.launcher-avatar {
  position: relative;
  width: 40px;
  height: 40px;
  flex: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.16);
  display: grid;
  place-items: center;
}

.launcher-icon {
  font-size: 19px;
  line-height: 1;
}

.launcher-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  text-align: left;
}

.launcher-text strong {
  font-size: 13.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.launcher-text small {
  font-size: 11px;
  opacity: 0.78;
}

.badge {
  position: absolute;
  top: -7px;
  right: -6px;
  min-width: 19px;
  height: 19px;
  padding: 0 5px;
  border-radius: 999px;
  border: 2px solid var(--panel);
  background: #d92d20;
  color: #fff;
  font-size: 11px;
  line-height: 15px;
  text-align: center;
  box-sizing: border-box;
}

.presence {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 2px solid var(--accent);
  background: #9aa0a6;
}

.launcher.active .presence {
  border-color: var(--accent-strong);
}

.presence.online {
  background: #12b76a;
}

.presence.connecting {
  background: #f79009;
}

@keyframes launcher-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(15, 118, 110, 0.38);
  }
  70% {
    box-shadow: 0 0 0 16px rgba(15, 118, 110, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(15, 118, 110, 0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .launcher::after {
    animation: none;
  }

  .launcher:hover {
    transform: none;
  }
}

.chat-box {
  width: 360px;
  height: 540px;
  max-height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: var(--shadow);
  overflow: hidden;
}

.chat-box-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}

.advisor-avatar {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  background: var(--accent);
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 600;
}

.advisor-meta {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  flex: 1;
}

.advisor-meta strong {
  font-size: 14px;
  color: var(--ink);
}

.conn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  color: var(--text-muted);
}

.conn .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #9aa0a6;
}

.conn.online .dot {
  background: #12b76a;
}

.conn.connecting .dot {
  background: #f79009;
}

.icon-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  font-size: 18px;
  cursor: pointer;
}

.icon-btn:hover {
  background: var(--panel-alt);
  color: var(--ink);
}

.chat-box-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--panel-alt);
}

.notice {
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
  padding: 4px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
}

.chat-empty {
  margin: auto 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: var(--text);
  font-size: 13px;
}

.quick-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quick-btn {
  text-align: left;
  padding: 9px 12px;
  border-radius: 10px;
  border: 1px dashed var(--line-strong);
  background: transparent;
  color: var(--text);
  font-size: 12.5px;
  cursor: pointer;
}

.quick-btn:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.row {
  display: flex;
}

.row.mine {
  justify-content: flex-end;
}

.bubble {
  max-width: 82%;
  padding: 9px 12px;
  border-radius: 4px 12px 12px 12px;
  background: #fff;
  border: 1px solid var(--line);
  font-size: 13.5px;
  line-height: 1.6;
  word-break: break-word;
}

.row.mine .bubble {
  background: var(--accent);
  border-color: transparent;
  color: #fff;
  border-radius: 12px 4px 12px 12px;
}

.content {
  margin: 0;
  white-space: pre-wrap;
}

.meta {
  display: block;
  margin-top: 3px;
  font-size: 10.5px;
  opacity: 0.6;
}

.chat-error {
  padding: 6px 16px;
  font-size: 12px;
  color: #b42318;
  background: #fdecec;
}

.chat-box-foot {
  border-top: 1px solid var(--line);
  padding: 10px 12px 12px;
}

.offline-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #b25a1c;
  background: #fff6e5;
  border-radius: 8px;
  padding: 6px 10px;
  margin-bottom: 8px;
}

.retry-btn {
  border: none;
  background: transparent;
  color: var(--accent-strong);
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
}

.composer {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  border: 1px solid var(--line-strong);
  border-radius: 14px;
  padding: 6px 6px 6px 12px;
  background: #fff;
}

.composer:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}

.composer textarea {
  flex: 1;
  border: none;
  resize: none;
  font: inherit;
  font-size: 13.5px;
  line-height: 1.5;
  padding: 6px 0;
  max-height: 96px;
  background: transparent;
  color: var(--ink);
}

.composer textarea:focus {
  outline: none;
}

.send {
  padding: 8px 14px;
  border: none;
  border-radius: 10px;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.send:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}

@media (max-width: 520px) {
  .chat-widget {
    right: 12px;
    bottom: 12px;
  }

  .launcher {
    height: 54px;
    padding: 0 7px;
    gap: 0;
  }

  .launcher-text {
    display: none;
  }

  .launcher-avatar {
    width: 40px;
    height: 40px;
    background: transparent;
  }

  .chat-box {
    width: calc(100vw - 24px);
    height: calc(100vh - 120px);
  }
}
</style>
