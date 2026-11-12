<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '../api/http'
import { fetchCaptcha, loginAccount, registerAccount } from '../stores/auth'

type Mode = 'login' | 'register' | 'forgot' | 'reset'

const mode = ref<Mode>('login')
const busy = ref(false)
const message = ref('')
const error = ref('')

const captchaImage = ref('')
const captchaId = ref('')
const captchaCode = ref('')
const resetToken = ref('')
const resetPassword = ref('')

const form = reactive({
  username: '',
  password: '',
  nickname: '',
  email: '',
  phone: '',
  account: '',
})

const title = computed(() => {
  switch (mode.value) {
    case 'register':
      return '创建账号'
    case 'forgot':
      return '找回密码'
    case 'reset':
      return '重置密码'
    default:
      return '账号登录'
  }
})

const subtitle = computed(() => {
  switch (mode.value) {
    case 'register':
      return '注册后默认分配 USER 角色，由管理员进一步授权'
    case 'forgot':
      return '通过账号或邮箱获取一次性重置凭证'
    case 'reset':
      return '凭证 10 分钟内有效，使用后立即失效'
    default:
      return '登录成功后凭证写入 Redis，并按角色权限渲染菜单'
  }
})

async function loadCaptcha() {
  try {
    const data = await fetchCaptcha()
    captchaImage.value = data.image
    captchaId.value = data.captcha_id
    captchaCode.value = ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : '验证码加载失败'
  }
}

function switchMode(next: Mode) {
  mode.value = next
  error.value = ''
  message.value = ''
  void loadCaptcha()
}

function validateCaptcha(): boolean {
  if (!captchaCode.value.trim()) {
    error.value = '请输入图形验证码'
    return false
  }
  return true
}

async function submitLogin() {
  if (!validateCaptcha()) return
  busy.value = true
  error.value = ''
  try {
    await loginAccount({
      username: form.username.trim(),
      password: form.password,
      captcha_id: captchaId.value,
      captcha_code: captchaCode.value.trim(),
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : '登录失败'
    await loadCaptcha()
  } finally {
    busy.value = false
  }
}

async function submitRegister() {
  if (!validateCaptcha()) return
  busy.value = true
  error.value = ''
  try {
    await registerAccount({
      username: form.username.trim(),
      password: form.password,
      nickname: form.nickname.trim() || null,
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      captcha_id: captchaId.value,
      captcha_code: captchaCode.value.trim(),
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : '注册失败'
    await loadCaptcha()
  } finally {
    busy.value = false
  }
}

async function submitForgot() {
  if (!validateCaptcha()) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const data = await request<{ reset_token: string | null; expires_in: number }>(
      '/auth/password/forgot',
      {
        method: 'POST',
        data: {
          account: form.account.trim(),
          captcha_id: captchaId.value,
          captcha_code: captchaCode.value.trim(),
        },
      },
    )
    if (data.reset_token) {
      resetToken.value = data.reset_token
      message.value = '重置凭证已生成，请设置新密码'
      mode.value = 'reset'
    } else {
      message.value = '如果账号存在，重置凭证已生成（演示环境仅对已注册账号返回凭证）'
      await loadCaptcha()
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '找回密码失败'
    await loadCaptcha()
  } finally {
    busy.value = false
  }
}

async function submitReset() {
  if (!resetPassword.value.trim()) {
    error.value = '请输入新密码'
    return
  }
  busy.value = true
  error.value = ''
  try {
    await request('/auth/password/reset', {
      method: 'POST',
      data: { reset_token: resetToken.value, new_password: resetPassword.value },
    })
    message.value = '密码已重置，请使用新密码登录'
    mode.value = 'login'
    form.username = form.account || form.username
    form.password = ''
    await loadCaptcha()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '重置失败'
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  void loadCaptcha()
})
</script>

<template>
  <div class="auth-page">
    <section class="auth-brand">
      <div class="brand-mark">TP</div>
      <h1>旅行规划智能体 · 管理控制台</h1>
      <p>
        RBAC 权限模型、Redis 会话凭证、接口级鉴权与动态菜单，全部在同一条登录链路中完成。
      </p>
      <ul class="brand-points">
        <li><span>01</span>登录前预置角色、菜单与接口权限</li>
        <li><span>02</span>验证码 + 限流 + 失败锁定三重防刷</li>
        <li><span>03</span>令牌与权限快照写入 Redis 并设置过期</li>
        <li><span>04</span>接口拦截与权限缓存支撑动态菜单</li>
      </ul>
      <div class="brand-foot">演示账号 admin / Admin@123456 · traveler / Traveler@123456</div>
    </section>

    <section class="auth-panel">
      <div class="auth-card">
        <header>
          <span class="auth-tag">ADMIN CONSOLE</span>
          <h2>{{ title }}</h2>
          <p>{{ subtitle }}</p>
        </header>

        <div class="auth-tabs">
          <button
            type="button"
            :class="{ active: mode === 'login' }"
            @click="switchMode('login')"
          >
            登录
          </button>
          <button
            type="button"
            :class="{ active: mode === 'register' }"
            @click="switchMode('register')"
          >
            注册
          </button>
          <button
            type="button"
            :class="{ active: mode === 'forgot' || mode === 'reset' }"
            @click="switchMode('forgot')"
          >
            忘记密码
          </button>
        </div>

        <div v-if="message" class="auth-note success">{{ message }}</div>
        <div v-if="error" class="auth-note error">{{ error }}</div>

        <form v-if="mode === 'login'" class="auth-form" @submit.prevent="submitLogin">
          <label>
            用户名
            <input v-model="form.username" name="username" autocomplete="username" spellcheck="false" placeholder="请输入用户名" />
          </label>
          <label>
            密码
            <input
              v-model="form.password"
              name="password"
              type="password"
              autocomplete="current-password"
              placeholder="请输入密码"
            />
          </label>
          <div class="captcha-row">
            <label>
              验证码
              <input v-model="captchaCode" name="captcha_code" maxlength="8" autocomplete="off" spellcheck="false" placeholder="输入图中字符" />
            </label>
            <button type="button" class="captcha-btn" aria-label="刷新图形验证码" title="点击刷新" @click="loadCaptcha">
              <img v-if="captchaImage" :src="captchaImage" alt="图形验证码" width="120" height="42" />
              <span v-else>加载中…</span>
            </button>
          </div>
          <button type="submit" class="primary-btn" :disabled="busy">
            {{ busy ? '登录中…' : '登录控制台' }}
          </button>
        </form>

        <form v-else-if="mode === 'register'" class="auth-form" @submit.prevent="submitRegister">
          <label>
            用户名
            <input v-model="form.username" name="username" autocomplete="username" spellcheck="false" placeholder="3-32 位字母、数字或下划线" />
          </label>
          <div class="form-grid">
            <label>
              密码
              <input v-model="form.password" name="password" type="password" autocomplete="new-password" placeholder="至少 8 位，含字母与数字" />
            </label>
            <label>
              昵称
              <input v-model="form.nickname" name="nickname" autocomplete="nickname" placeholder="可选" />
            </label>
            <label>
              邮箱
              <input v-model="form.email" name="email" type="email" autocomplete="email" spellcheck="false" placeholder="可选，用于找回密码" />
            </label>
            <label>
              手机号
              <input v-model="form.phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="可选" />
            </label>
          </div>
          <div class="captcha-row">
            <label>
              验证码
              <input v-model="captchaCode" name="captcha_code" maxlength="8" autocomplete="off" spellcheck="false" placeholder="输入图中字符" />
            </label>
            <button type="button" class="captcha-btn" aria-label="刷新图形验证码" title="点击刷新" @click="loadCaptcha">
              <img v-if="captchaImage" :src="captchaImage" alt="图形验证码" width="120" height="42" />
              <span v-else>加载中…</span>
            </button>
          </div>
          <button type="submit" class="primary-btn" :disabled="busy">
            {{ busy ? '提交中…' : '注册并登录' }}
          </button>
        </form>

        <form v-else-if="mode === 'forgot'" class="auth-form" @submit.prevent="submitForgot">
          <label>
            账号或邮箱
            <input v-model="form.account" name="account" autocomplete="username" spellcheck="false" placeholder="请输入注册时的用户名或邮箱" />
          </label>
          <div class="captcha-row">
            <label>
              验证码
              <input v-model="captchaCode" name="captcha_code" maxlength="8" autocomplete="off" spellcheck="false" placeholder="输入图中字符" />
            </label>
            <button type="button" class="captcha-btn" aria-label="刷新图形验证码" title="点击刷新" @click="loadCaptcha">
              <img v-if="captchaImage" :src="captchaImage" alt="图形验证码" width="120" height="42" />
              <span v-else>加载中…</span>
            </button>
          </div>
          <button type="submit" class="primary-btn" :disabled="busy">
            {{ busy ? '提交中…' : '获取重置凭证' }}
          </button>
          <p class="form-hint">同一 IP 5 分钟内最多提交 5 次，防止批量刷取。</p>
        </form>

        <form v-else class="auth-form" @submit.prevent="submitReset">
          <label>
            重置凭证
            <input v-model="resetToken" readonly />
          </label>
          <label>
            新密码
            <input v-model="resetPassword" type="password" placeholder="至少 8 位，含字母与数字" />
          </label>
          <button type="submit" class="primary-btn" :disabled="busy">
            {{ busy ? '提交中…' : '确认重置' }}
          </button>
          <p class="form-hint">重置成功后该账号所有 Redis 会话立即失效，需要重新登录。</p>
        </form>

        <footer class="auth-footer">
          登录接口 /api/v1/auth/login · 凭证与会话由 Redis 托管
        </footer>
      </div>
    </section>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(420px, 1.1fr);
  background: var(--bg);
}

.auth-brand {
  padding: 64px 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
  color: #e2f5f2;
  background: linear-gradient(160deg, #0a3a35, #07211f 70%);
}

.brand-mark {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  font-weight: 800;
  letter-spacing: 1px;
  color: #0b5d57;
  background: #e6f6f3;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.35);
}

.auth-brand h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.25;
}

.auth-brand p {
  margin: 0;
  max-width: 440px;
  color: rgba(226, 245, 242, 0.78);
  font-size: 14px;
  line-height: 1.8;
}

.brand-points {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 440px;
}

.brand-points li {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13.5px;
  color: rgba(226, 245, 242, 0.9);
}

.brand-points span {
  width: 26px;
  height: 26px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
  color: #073f3a;
  background: rgba(94, 234, 212, 0.9);
}

.brand-foot {
  margin-top: 18px;
  font-size: 12px;
  color: rgba(226, 245, 242, 0.6);
}

.auth-panel {
  display: grid;
  place-items: center;
  padding: 40px 24px;
}

.auth-card {
  width: min(520px, 100%);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 30px 32px 22px;
  box-shadow: var(--shadow);
}

.auth-tag {
  font-size: 10.5px;
  letter-spacing: 2px;
  color: var(--accent-strong);
  font-weight: 700;
}

.auth-card h2 {
  margin: 8px 0 6px;
  font-size: 23px;
  color: var(--ink);
}

.auth-card header p {
  margin: 0;
  font-size: 12.5px;
  color: var(--muted);
  line-height: 1.7;
}

.auth-tabs {
  display: flex;
  gap: 6px;
  margin: 20px 0 16px;
  padding: 4px;
  border-radius: 12px;
  background: var(--panel-alt);
}

.auth-tabs button {
  flex: 1;
  padding: 8px 10px;
  border: none;
  border-radius: 9px;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--muted);
  cursor: pointer;
}

.auth-tabs button.active {
  background: #fff;
  color: var(--accent-strong);
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
}

.auth-note {
  margin-bottom: 14px;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 12.5px;
  line-height: 1.6;
}

.auth-note.success {
  color: #065f46;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.auth-note.error {
  color: #991b1b;
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 13px;
}

.auth-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12.5px;
  color: var(--muted);
}

.auth-form input {
  font: inherit;
  font-size: 14px;
  color: var(--ink);
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--line-strong);
  background: #fff;
}

.auth-form input:focus {
  outline: 2px solid var(--ring);
  border-color: var(--accent);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.captcha-row {
  display: grid;
  grid-template-columns: 1fr 132px;
  gap: 10px;
  align-items: end;
}

.captcha-btn {
  height: 40px;
  border: 1px solid var(--line-strong);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  overflow: hidden;
  padding: 0;
}

.captcha-btn img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.primary-btn {
  margin-top: 6px;
  padding: 11px 16px;
  border: none;
  border-radius: 11px;
  background: var(--accent);
  color: #fff;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.primary-btn:hover:not(:disabled) {
  background: var(--accent-strong);
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-hint {
  margin: 2px 0 0;
  font-size: 11.5px;
  color: var(--muted);
  line-height: 1.6;
}

.auth-footer {
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
  font-size: 11.5px;
  color: var(--muted);
}

.auth-footer code {
  background: var(--panel-alt);
  padding: 1px 5px;
  border-radius: 4px;
}

@media (max-width: 900px) {
  .auth-page {
    grid-template-columns: 1fr;
  }

  .auth-brand {
    padding: 40px 28px;
  }

  .auth-brand h1 {
    font-size: 24px;
  }
}
</style>
