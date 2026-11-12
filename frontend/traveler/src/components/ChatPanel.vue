<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Message, SlotInfo, ToolCallInfo } from '../api/types'
import { renderMarkdownLite, timeText } from '../utils/format'

const props = defineProps<{
  messages: Message[]
  draft: string
  streaming: boolean
  slots: Record<string, SlotInfo>
  missingSlots: string[]
  toolCalls: ToolCallInfo[]
  degraded: string[]
  error: string | null
  disabled: boolean
}>()

const emit = defineEmits<{ (e: 'send', content: string): void }>()

const input = ref('')
const scroller = ref<HTMLElement | null>(null)

const examples = [
  '从杭州出发去云南玩 5 天，2 个人，预算 8000 元，想慢节奏',
  '国庆从上海去西安 4 天，3 人，人文历史，预算 1 万',
  '成都出发去三亚 6 天 5 晚，亲子游，住得离海边近一点',
]

const slotEntries = computed(() => Object.values(props.slots))
const toolEntries = computed(() => props.toolCalls)

function submit() {
  const text = input.value.trim()
  if (!text || props.streaming || props.disabled) return
  emit('send', text)
  input.value = ''
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}

watch(
  () => [props.messages.length, props.draft, props.error],
  async () => {
    await nextTick()
    const el = scroller.value
    if (el) el.scrollTop = el.scrollHeight
  },
)
</script>

<template>
  <section class="chat-panel">
    <header class="chat-head">
      <div>
        <h2>对话规划</h2>
        <p class="muted">说出出发地、目的地、天数、人数和预算，我来生成完整行程。</p>
        <p v-if="missingSlots.length" class="missing-hint">
          还需补充 {{ missingSlots.length }} 项必要信息
        </p>
      </div>
      <div v-if="slotEntries.length" class="slot-bar">
        <span
          v-for="slot in slotEntries"
          :key="slot.label"
          class="slot-chip"
          :class="{ missing: slot.required && !slot.filled }"
          :title="slot.value || '待补充'"
        >
          {{ slot.label }}：{{ slot.value || '待补充' }}
        </span>
      </div>
    </header>

    <div ref="scroller" class="chat-scroll">
      <div v-if="!messages.length && !draft" class="chat-empty">
        <h3>把旅行想法告诉我</h3>
        <p class="muted">例如：从杭州出发，去大理丽江 6 天 5 晚，两个人，预算一万，节奏慢一点。</p>
        <div class="example-list">
          <button
            v-for="example in examples"
            :key="example"
            type="button"
            class="example-btn"
            :disabled="disabled"
            @click="emit('send', example)"
          >
            {{ example }}
          </button>
        </div>
      </div>

      <div v-for="message in messages" :key="message.id" class="bubble-row" :class="message.role.toLowerCase()">
        <div class="avatar">{{ message.role === 'USER' ? '我' : 'AI' }}</div>
        <div class="bubble">
          <div
            v-if="message.role === 'ASSISTANT'"
            class="markdown"
            v-html="renderMarkdownLite(message.content)"
          />
          <p v-else class="plain">{{ message.content }}</p>
          <span class="bubble-time">{{ timeText(message.created_at?.slice(11)) }}</span>
        </div>
      </div>

      <div v-if="streaming || draft" class="bubble-row assistant">
        <div class="avatar">AI</div>
        <div class="bubble">
          <div class="markdown" v-html="renderMarkdownLite(draft || '正在思考…')" />
          <span v-if="streaming" class="typing-dot">生成中</span>
        </div>
      </div>

      <div v-if="error" class="alert error">{{ error }}</div>
    </div>

    <div v-if="toolEntries.length || degraded.length" class="tool-strip">
      <span v-for="tool in toolEntries" :key="tool.call_id" class="tool-chip" :class="{ off: tool.degrade }">
        {{ tool.tool_type }} · {{ tool.status }} · {{ tool.result_count }} 条
      </span>
      <span v-if="degraded.length" class="tool-chip off">
        降级：{{ degraded.join(' / ') }}
      </span>
    </div>

    <div class="composer">
      <textarea
        v-model="input"
        rows="2"
        placeholder="例如：帮我加一天，住得离景区近一点"
        :disabled="disabled || streaming"
        @keydown="onKeydown"
      />
      <button type="button" class="send-btn" :disabled="disabled || streaming || !input.trim()" @click="submit">
        {{ streaming ? '生成中…' : '发送' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: var(--panel);
  border-right: 1px solid var(--line);
}

.chat-head {
  padding: 20px 22px 14px;
  border-bottom: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-head h2 {
  margin: 0;
  font-size: 18px;
}

.chat-head p {
  margin: 4px 0 0;
  font-size: 13px;
}

.chat-head p.missing-hint {
  font-size: 11.5px;
  color: #a9681a;
}

.slot-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.slot-chip {
  font-size: 12px;
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-strong);
  border: 1px solid transparent;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.slot-chip.missing {
  background: #fff6e5;
  color: #a9681a;
  border-color: #f5d9a8;
}

.chat-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px max(24px, calc((100% - 820px) / 2));
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chat-empty {
  margin: auto 0;
  text-align: left;
}

.chat-empty h3 {
  margin: 0 0 6px;
  font-size: 16px;
}

.example-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

.example-btn {
  text-align: left;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px dashed var(--line-strong);
  background: transparent;
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.example-btn:hover:not(:disabled) {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.bubble-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.bubble-row.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 9px;
  background: var(--ink);
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 11.5px;
  font-weight: 600;
  flex-shrink: 0;
}

.bubble-row.assistant .avatar {
  background: var(--accent);
}

.bubble {
  max-width: min(600px, 84%);
  padding: 11px 15px;
  border-radius: 4px 14px 14px 14px;
  background: #fff;
  border: 1px solid var(--line);
  font-size: 14px;
  line-height: 1.68;
  word-break: break-word;
}

.bubble-row.user .bubble {
  background: var(--accent);
  color: #fff;
  border-color: transparent;
  border-radius: 14px 4px 14px 14px;
}

.bubble-time {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  opacity: 0.55;
}

.plain {
  margin: 0;
  white-space: pre-wrap;
}

.markdown :deep(p) {
  margin: 0 0 8px;
}

.markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown :deep(strong) {
  color: var(--ink);
}

.bubble-row.user .markdown :deep(strong) {
  color: #fff;
}

.markdown :deep(code) {
  background: rgba(15, 118, 110, 0.1);
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 12px;
}

.typing-dot {
  display: inline-block;
  margin-top: 6px;
  font-size: 11px;
  color: var(--accent-strong);
}

.alert {
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13px;
}

.alert.error {
  background: #fdecec;
  color: #b42318;
  border: 1px solid #f6c7c4;
}

.tool-strip {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding: 8px 22px 0;
  border-top: 1px solid var(--line);
}

.tool-chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.tool-chip.off {
  background: #fff1e6;
  color: #b25a1c;
}

.composer {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  margin: 0 max(24px, calc((100% - 820px) / 2)) 20px;
  padding: 8px 8px 8px 14px;
  background: #fff;
  border: 1px solid var(--line-strong);
  border-radius: 16px;
  box-shadow: 0 12px 26px -22px rgba(15, 23, 42, 0.5);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.composer:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}

.composer textarea {
  flex: 1;
  resize: none;
  border: none;
  padding: 8px 0;
  font: inherit;
  font-size: 14px;
  background: transparent;
  color: var(--ink);
  line-height: 1.5;
}

.composer textarea:focus,
.composer textarea:focus-visible {
  outline: none;
}

.send-btn {
  padding: 10px 18px;
  border-radius: 12px;
  border: none;
  background: var(--accent);
  color: #fff;
  font: inherit;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  min-width: 78px;
  transition: background 0.15s;
}

.send-btn:hover:not(:disabled) {
  background: var(--accent-strong);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
