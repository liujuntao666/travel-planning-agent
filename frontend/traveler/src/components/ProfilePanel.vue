<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { api } from '../api/client'
import type { UserTagItem } from '../api/client'
import type { User } from '../api/types'
import { formatDateTime } from '../utils/format'

const props = defineProps<{ user: User }>()
const emit = defineEmits<{
  close: []
  updated: [user: User]
  logout: []
}>()

const panelEl = ref<HTMLElement | null>(null)
const loading = ref(true)
const info = ref<User>(props.user)
const roles = ref<string[]>([])
const sessionCount = ref(0)
const sessionBackend = ref('')

const form = reactive({
  nickname: props.user.nickname || props.user.username || '',
  email: props.user.email || '',
  phone: props.user.phone || '',
})
const saving = ref(false)
const formError = ref('')
const formSuccess = ref('')

const pwd = reactive({ old: '', next: '', confirm: '' })
const pwdSaving = ref(false)
const pwdError = ref('')
const pwdSuccess = ref('')

const tags = ref<UserTagItem[]>([])
const tagsLoading = ref(false)
const tagsMsg = ref('')

const tagGroups = computed(() => {
  const groups = new Map<string, UserTagItem[]>()
  for (const tag of tags.value) {
    const list = groups.get(tag.category) || []
    list.push(tag)
    groups.set(tag.category, list)
  }
  return [...groups.entries()].map(([category, items]) => ({ category, items }))
})

async function loadTags() {
  tagsLoading.value = true
  try {
    const result = await api.myTags()
    tags.value = result.items
    // 首次进入且尚无标签时自动打标一次，之后由用户手动刷新
    if (!result.total) {
      const refreshed = await api.refreshTags()
      tags.value = refreshed.items
    }
  } catch {
    // 标签属于增强信息，读取失败不影响资料编辑
  } finally {
    tagsLoading.value = false
  }
}

async function refreshTags() {
  tagsLoading.value = true
  tagsMsg.value = ''
  try {
    const result = await api.refreshTags()
    tags.value = result.items
    tagsMsg.value = result.total ? result.message : '暂无可生成的标签'
  } catch (err) {
    tagsMsg.value = err instanceof Error ? err.message : '刷新失败'
  } finally {
    tagsLoading.value = false
  }
}

async function clearTags() {
  if (!window.confirm('确定清除全部标签吗？清除后不再用于站内推荐，可随时重新生成。')) return
  tagsLoading.value = true
  tagsMsg.value = ''
  try {
    const result = await api.clearTags()
    tags.value = []
    tagsMsg.value = result.message
  } catch (err) {
    tagsMsg.value = err instanceof Error ? err.message : '清除失败'
  } finally {
    tagsLoading.value = false
  }
}

const avatarText = computed(() => (info.value.nickname || info.value.username || '旅').slice(0, 1))
const displayName = computed(() => info.value.nickname || info.value.username || '旅行者')
const account = computed(() => info.value.username || info.value.open_id)
const roleLabel = computed(() =>
  roles.value.length ? roles.value.join(' / ') : info.value.role || 'USER',
)
const lastLogin = computed(() => formatDateTime(info.value.last_login_at) || '暂无记录')

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  await nextTick()
  panelEl.value?.focus()
  try {
    const session = await api.me()
    info.value = session.user
    roles.value = session.roles
    sessionCount.value = session.session?.count ?? 0
    sessionBackend.value = session.session?.backend ?? ''
    form.nickname = session.user.nickname || session.user.username || ''
    form.email = session.user.email || ''
    form.phone = session.user.phone || ''
  } catch {
    // 读取失败时沿用登录时返回的用户信息
  } finally {
    loading.value = false
  }
  void loadTags()
})

onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

const openedAt = Date.now()

const dirty = computed(
  () =>
    form.nickname !== (info.value.nickname || info.value.username || '') ||
    form.email !== (info.value.email || '') ||
    form.phone !== (info.value.phone || '') ||
    Boolean(pwd.old || pwd.next || pwd.confirm),
)

function onMaskClick() {
  // 打开瞬间的点击（例如双击侧栏头像的第二下）或存在未保存修改时，不关闭面板
  if (Date.now() - openedAt < 250) return
  if (dirty.value) return
  emit('close')
}

function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Escape') return
  // 输入法候选、浏览器自动填充下拉的 Esc 只用于取消它们，不能顺手关闭面板
  if (event.isComposing || event.keyCode === 229) return
  const active = document.activeElement as HTMLElement | null
  if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) {
    active.blur()
    return
  }
  if (dirty.value) return
  emit('close')
}

async function saveProfile() {
  formError.value = ''
  formSuccess.value = ''
  const nickname = form.nickname.trim()
  if (!nickname) {
    formError.value = '昵称不能为空'
    return
  }
  saving.value = true
  try {
    const result = await api.updateProfile({
      nickname,
      email: form.email.trim(),
      phone: form.phone.trim(),
    })
    info.value = result.user
    form.nickname = result.user.nickname || ''
    form.email = result.user.email || ''
    form.phone = result.user.phone || ''
    formSuccess.value = result.message
    emit('updated', result.user)
  } catch (err) {
    formError.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function savePassword() {
  pwdError.value = ''
  pwdSuccess.value = ''
  if (!pwd.old) {
    pwdError.value = '请输入原密码'
    return
  }
  if (pwd.next.length < 8) {
    pwdError.value = '新密码至少 8 位'
    return
  }
  if (!/[A-Za-z]/.test(pwd.next) || !/\d/.test(pwd.next)) {
    pwdError.value = '新密码需同时包含字母与数字'
    return
  }
  if (pwd.next !== pwd.confirm) {
    pwdError.value = '两次输入的新密码不一致'
    return
  }
  pwdSaving.value = true
  try {
    const result = await api.changePassword(pwd.old, pwd.next)
    pwdSuccess.value = result.message
    pwd.old = ''
    pwd.next = ''
    pwd.confirm = ''
    if (result.revoked_sessions > 0) sessionCount.value = 1
  } catch (err) {
    pwdError.value = err instanceof Error ? err.message : '修改失败'
  } finally {
    pwdSaving.value = false
  }
}
</script>

<template>
  <div class="pf-mask" @click.self="onMaskClick">
    <section
      ref="panelEl"
      class="pf-panel"
      role="dialog"
      aria-modal="true"
      aria-labelledby="pf-title"
      tabindex="-1"
    >
      <header class="pf-head">
        <div>
          <h2 id="pf-title">个人信息</h2>
          <p class="pf-sub">账号资料与登录安全</p>
        </div>
        <button type="button" class="pf-close" aria-label="关闭个人信息面板" @click="emit('close')">
          ×
        </button>
      </header>

      <div class="pf-body">
        <div class="pf-identity">
          <span class="pf-avatar" aria-hidden="true">{{ avatarText }}</span>
          <div class="pf-identity-text">
            <span class="pf-name">{{ displayName }}</span>
            <span class="pf-account">{{ account }}</span>
          </div>
          <span class="pf-role">{{ roleLabel }}</span>
        </div>

        <dl class="pf-meta">
          <div>
            <dt>最近登录</dt>
            <dd>{{ lastLogin }}</dd>
          </div>
          <div>
            <dt>在线设备</dt>
            <dd>{{ loading ? '读取中…' : `${sessionCount} 个会话` }}</dd>
          </div>
          <div>
            <dt>会话存储</dt>
            <dd>{{ sessionBackend || 'redis' }}</dd>
          </div>
        </dl>

        <section class="pf-tags" aria-labelledby="pf-tags-title">
          <div class="pf-tags-head">
            <h3 id="pf-tags-title">我的标签</h3>
            <div class="pf-tags-ops">
              <button type="button" class="pf-link" :disabled="tagsLoading" @click="refreshTags">
                {{ tagsLoading ? '处理中…' : '刷新' }}
              </button>
              <button
                v-if="tags.length"
                type="button"
                class="pf-link pf-link--muted"
                :disabled="tagsLoading"
                @click="clearTags"
              >
                清除
              </button>
            </div>
          </div>
          <p class="pf-tags-note">依据你的行程与操作自动生成，仅用于站内推荐，可随时清除。</p>
          <p v-if="!tags.length && !tagsLoading" class="pf-tags-empty">
            还没有足够数据生成标签，先规划一次行程吧。
          </p>
          <div v-else class="pf-tags-groups">
            <div v-for="group in tagGroups" :key="group.category" class="pf-tags-group">
              <span class="pf-tags-cat">{{ group.category }}</span>
              <div class="pf-tags-list">
                <span
                  v-for="tag in group.items"
                  :key="tag.tag_code"
                  class="pf-tag"
                  :title="tag.description || tag.tag_name"
                >
                  {{ tag.tag_name }}
                  <em>{{ Math.round(tag.score) }}</em>
                </span>
              </div>
            </div>
          </div>
          <p v-if="tagsMsg" class="pf-msg pf-msg--ok">{{ tagsMsg }}</p>
        </section>

        <form class="pf-form" @submit.prevent="saveProfile">
          <h3>基本资料</h3>
          <label>
            昵称
            <input v-model="form.nickname" name="nickname" type="text" maxlength="64" autocomplete="nickname" />
          </label>
          <label>
            邮箱
            <input
              v-model="form.email"
              name="email"
              type="email"
              maxlength="128"
              autocomplete="email"
              spellcheck="false"
              placeholder="用于找回密码，可留空"
            />
          </label>
          <label>
            手机号
            <input
              v-model="form.phone"
              name="phone"
              type="tel"
              maxlength="32"
              autocomplete="tel"
              spellcheck="false"
              placeholder="6-20 位数字，可留空"
            />
          </label>
          <p v-if="formError" class="pf-msg pf-msg--error" role="alert">{{ formError }}</p>
          <p v-if="formSuccess" class="pf-msg pf-msg--ok" role="status">{{ formSuccess }}</p>
          <div class="pf-actions">
            <button type="submit" class="pf-btn pf-btn--primary" :disabled="saving || loading">
              {{ saving ? '保存中…' : '保存资料' }}
            </button>
          </div>
        </form>

        <form class="pf-form" @submit.prevent="savePassword">
          <h3>修改密码</h3>
          <label>
            原密码
            <input v-model="pwd.old" name="old-password" type="password" autocomplete="current-password" />
          </label>
          <label>
            新密码
            <input
              v-model="pwd.next"
              name="new-password"
              type="password"
              autocomplete="new-password"
              placeholder="至少 8 位，含字母与数字"
            />
          </label>
          <label>
            确认新密码
            <input v-model="pwd.confirm" name="confirm-password" type="password" autocomplete="new-password" />
          </label>
          <p v-if="pwdError" class="pf-msg pf-msg--error" role="alert">{{ pwdError }}</p>
          <p v-if="pwdSuccess" class="pf-msg pf-msg--ok" role="status">{{ pwdSuccess }}</p>
          <div class="pf-actions">
            <button type="submit" class="pf-btn pf-btn--primary" :disabled="pwdSaving">
              {{ pwdSaving ? '提交中…' : '更新密码' }}
            </button>
          </div>
        </form>
      </div>

      <footer class="pf-foot">
        <button type="button" class="pf-btn pf-btn--danger" @click="emit('logout')">退出登录</button>
        <button type="button" class="pf-btn" @click="emit('close')">关闭</button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.pf-mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.38);
  backdrop-filter: blur(2px);
}

.pf-panel {
  width: min(480px, 100%);
  max-height: min(88vh, 760px);
  display: flex;
  flex-direction: column;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 28px 60px -32px rgba(15, 23, 42, 0.45);
  outline: none;
}

.pf-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 22px 14px;
  border-bottom: 1px solid var(--line);
}

.pf-head h2 {
  font-size: 16px;
  line-height: 1.4;
}

.pf-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
}

.pf-close {
  border: none;
  background: none;
  font-size: 20px;
  line-height: 1;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 6px;
}

.pf-close:hover {
  background: var(--panel-alt);
  color: var(--ink);
}

.pf-body {
  padding: 18px 22px;
  overflow-y: auto;
}

.pf-identity {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pf-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent-strong);
  display: grid;
  place-items: center;
  font-size: 18px;
  flex-shrink: 0;
}

.pf-identity-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.pf-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pf-account {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pf-role {
  font-size: 11px;
  letter-spacing: 0.02em;
  color: var(--accent-strong);
  background: var(--accent-soft);
  border-radius: 999px;
  padding: 3px 10px;
  white-space: nowrap;
}

.pf-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 16px 0 4px;
  padding: 12px 14px;
  background: var(--panel-alt);
  border: 1px solid var(--line);
  border-radius: 12px;
}

.pf-meta dt {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.pf-meta dd {
  margin: 0;
  font-size: 12.5px;
  color: var(--ink);
  overflow-wrap: anywhere;
}

.pf-tags {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.pf-tags-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.pf-tags-head h3 {
  font-size: 13px;
}

.pf-tags-ops {
  display: flex;
  gap: 10px;
}

.pf-link {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  font-size: 12px;
  color: var(--accent-strong);
  cursor: pointer;
}

.pf-link:hover {
  text-decoration: underline;
}

.pf-link:disabled {
  color: var(--text-muted);
  cursor: default;
  text-decoration: none;
}

.pf-link--muted {
  color: var(--text-muted);
}

.pf-tags-note {
  margin: 6px 0 10px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--text-muted);
}

.pf-tags-empty {
  font-size: 12px;
  color: var(--text-muted);
}

.pf-tags-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pf-tags-group {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.pf-tags-cat {
  flex-shrink: 0;
  width: 64px;
  padding-top: 3px;
  font-size: 11.5px;
  color: var(--text-muted);
}

.pf-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pf-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  font-size: 12px;
  color: var(--ink);
  background: var(--panel-alt);
  border: 1px solid var(--line);
  border-radius: 999px;
}

.pf-tag em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--text-muted);
}

.pf-form {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.pf-form h3 {
  font-size: 13px;
  margin-bottom: 10px;
}

.pf-form label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.pf-form input {
  display: block;
  width: 100%;
  margin-top: 4px;
  padding: 8px 10px;
  font: inherit;
  font-size: 13px;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-radius: 8px;
}

.pf-form input:focus-visible {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}

.pf-msg {
  font-size: 12px;
  margin: 2px 0 10px;
}

.pf-msg--error {
  color: #b91c1c;
}

.pf-msg--ok {
  color: var(--accent-strong);
}

.pf-actions {
  display: flex;
  justify-content: flex-end;
}

.pf-btn {
  border: 1px solid var(--line-strong);
  background: var(--panel);
  color: var(--ink);
  font: inherit;
  font-size: 12.5px;
  padding: 7px 14px;
  border-radius: 8px;
  cursor: pointer;
}

.pf-btn:hover {
  background: var(--panel-alt);
}

.pf-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.pf-btn--primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.pf-btn--primary:hover {
  background: var(--accent-strong);
}

.pf-btn--danger {
  color: #b91c1c;
  border-color: #f0d5d5;
}

.pf-btn--danger:hover {
  background: #fdf3f3;
}

.pf-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 22px;
  border-top: 1px solid var(--line);
}

@media (max-width: 520px) {
  .pf-mask {
    padding: 12px;
  }

  .pf-panel {
    max-height: 92vh;
  }

  .pf-meta {
    grid-template-columns: 1fr;
    gap: 8px;
  }
}
</style>
