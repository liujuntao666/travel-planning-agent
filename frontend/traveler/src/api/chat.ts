import { API_BASE, getToken } from './http'

export type ChatRole = 'USER' | 'ADVISOR' | 'SYSTEM'
export type ChatStatus = 'connecting' | 'online' | 'offline'

export interface ChatMessage {
  id: number
  seq: number
  sender_id: number | null
  sender_role: ChatRole
  content: string
  client_id?: string | null
  read_flag: number
  created_at: string | null
  status?: 'sending' | 'sent' | 'failed'
}

export interface ChatThreadInfo {
  thread_id: number
  title: string | null
  last_seq: number
  last_message_at: string | null
  unread: number
  online: boolean
}

interface ChatClientOptions {
  threadId: number
  onMessage: (message: ChatMessage) => void
  onAck: (clientId: string, seq: number, id: number) => void
  onFailed: (clientId: string) => void
  onSync: (messages: ChatMessage[]) => void
  onRead: (seq: number) => void
  onStatus: (status: ChatStatus) => void
  onError: (message: string) => void
}

const HEARTBEAT_MS = 30_000
const PONG_TIMEOUT_MS = 10_000
const ACK_TIMEOUT_MS = 3_000
const MAX_RETRY_DELAY_MS = 30_000

function wsUrl(threadId: number, token: string): string {
  const base = API_BASE.replace(/^http/i, 'ws')
  return `${base}/chat/ws?token=${encodeURIComponent(token)}&thread_id=${threadId}`
}

export function newClientId(): string {
  const cryptoObj = globalThis.crypto
  if (cryptoObj && 'randomUUID' in cryptoObj) return cryptoObj.randomUUID()
  return `c-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`
}

export class ChatClient {
  private ws: WebSocket | null = null
  private options: ChatClientOptions
  private retry = 0
  private closedByUser = false
  private heartbeatTimer = 0
  private pongTimer = 0
  private awaitingPong = false
  private reconnectTimer = 0
  private pending = new Map<string, { message: ChatMessage; attempts: number; timer: number }>()
  private lastSeq = 0

  constructor(options: ChatClientOptions) {
    this.options = options
  }

  connect(): void {
    this.closedByUser = false
    const token = getToken()
    if (!token) {
      this.options.onStatus('offline')
      return
    }
    this.options.onStatus('connecting')
    let socket: WebSocket
    try {
      socket = new WebSocket(wsUrl(this.options.threadId, token))
    } catch {
      this.scheduleReconnect()
      return
    }
    this.ws = socket

    socket.onopen = () => {
      this.retry = 0
      this.options.onStatus('online')
      this.startHeartbeat()
      this.requestSync()
      this.flushPending()
    }

    socket.onmessage = (event) => {
      if (event.data === 'pong') {
        this.awaitingPong = false
        return
      }
      let payload: Record<string, unknown>
      try {
        payload = JSON.parse(event.data) as Record<string, unknown>
      } catch {
        return
      }
      this.dispatch(payload)
    }

    socket.onclose = () => {
      this.stopHeartbeat()
      this.ws = null
      this.options.onStatus('offline')
      if (!this.closedByUser) this.scheduleReconnect()
    }

    socket.onerror = () => {
      this.options.onError('聊天连接异常，正在重试')
    }
  }

  close(): void {
    this.closedByUser = true
    this.stopHeartbeat()
    window.clearTimeout(this.reconnectTimer)
    for (const entry of this.pending.values()) window.clearTimeout(entry.timer)
    this.pending.clear()
    this.ws?.close(1000)
    this.ws = null
    this.options.onStatus('offline')
  }

  send(message: ChatMessage): void {
    if (!message.client_id) return
    this.pending.set(message.client_id, { message, attempts: 0, timer: 0 })
    this.pushPending(message.client_id)
  }

  read(seq: number): void {
    if (!seq) return
    this.transmit({ type: 'read', seq })
  }

  private dispatch(payload: Record<string, unknown>): void {
    const type = payload.type as string
    if (type === 'pong') {
      this.awaitingPong = false
      return
    }
    if (type === 'ready') {
      this.lastSeq = Number(payload.last_seq || 0)
      this.requestSync()
      return
    }
    if (type === 'ack') {
      const clientId = String(payload.client_id || '')
      const entry = this.pending.get(clientId)
      if (entry) {
        window.clearTimeout(entry.timer)
        this.pending.delete(clientId)
      }
      this.lastSeq = Math.max(this.lastSeq, Number(payload.seq || 0))
      this.options.onAck(clientId, Number(payload.seq || 0), Number(payload.id || 0))
      return
    }
    if (type === 'message') {
      const message = payload.message as ChatMessage
      if (!message) return
      if (message.seq > this.lastSeq + 1) this.requestSync()
      this.lastSeq = Math.max(this.lastSeq, message.seq)
      this.options.onMessage(message)
      return
    }
    if (type === 'sync') {
      const messages = (payload.messages as ChatMessage[]) || []
      for (const message of messages) {
        this.lastSeq = Math.max(this.lastSeq, message.seq)
      }
      this.options.onSync(messages)
      return
    }
    if (type === 'read') {
      this.options.onRead(Number(payload.seq || 0))
      return
    }
    if (type === 'error') {
      this.options.onError(String(payload.message || '消息发送失败'))
    }
  }

  private transmit(payload: Record<string, unknown>): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload))
      return
    }
    this.options.onStatus('offline')
    this.scheduleReconnect()
  }

  private requestSync(): void {
    this.transmit({ type: 'sync', last_seq: this.lastSeq })
  }

  private flushPending(): void {
    for (const clientId of this.pending.keys()) this.pushPending(clientId)
  }

  private pushPending(clientId: string): void {
    const entry = this.pending.get(clientId)
    if (!entry) return
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
    this.ws.send(
      JSON.stringify({
        type: 'send',
        client_id: clientId,
        content: entry.message.content,
      }),
    )
    entry.attempts += 1
    window.clearTimeout(entry.timer)
    entry.timer = window.setTimeout(() => {
      const current = this.pending.get(clientId)
      if (!current) return
      if (current.attempts >= 3) {
        this.pending.delete(clientId)
        this.options.onFailed(clientId)
        return
      }
      this.pushPending(clientId)
    }, ACK_TIMEOUT_MS)
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = window.setInterval(() => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
      this.awaitingPong = true
      this.ws.send(JSON.stringify({ type: 'ping' }))
      window.clearTimeout(this.pongTimer)
      this.pongTimer = window.setTimeout(() => {
        if (this.awaitingPong) {
          this.options.onError('心跳超时，正在重连')
          this.ws?.close()
        }
      }, PONG_TIMEOUT_MS)
    }, HEARTBEAT_MS)
  }

  private stopHeartbeat(): void {
    window.clearInterval(this.heartbeatTimer)
    window.clearTimeout(this.pongTimer)
    this.awaitingPong = false
  }

  private scheduleReconnect(): void {
    if (this.closedByUser) return
    this.options.onStatus('offline')
    const delay = Math.min(1000 * 2 ** this.retry, MAX_RETRY_DELAY_MS) + Math.random() * 300
    this.retry += 1
    window.clearTimeout(this.reconnectTimer)
    this.reconnectTimer = window.setTimeout(() => this.connect(), delay)
  }
}
