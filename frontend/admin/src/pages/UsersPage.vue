<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '../api/http'
import type { AdminUser, PageResult, Role, UserAuthz } from '../api/types'
import ModalDialog from '../components/ModalDialog.vue'
import { hasPermission } from '../stores/auth'

const rows = ref<AdminUser[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const roleCode = ref('')
const status = ref('')
const sort = ref('id:desc')
const loading = ref(false)
const error = ref('')

const roleOptions = ref<Role[]>([])
const assignOpen = ref(false)
const assignUser = ref<AdminUser | null>(null)
const selectedRoleIds = ref<number[]>([])
const assignBusy = ref(false)

const authzOpen = ref(false)
const authzUser = ref<AdminUser | null>(null)
const authz = ref<UserAuthz | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await request<PageResult<AdminUser>>('/admin/users', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        keyword: keyword.value.trim(),
        role_code: roleCode.value,
        status: status.value,
        sort: sort.value,
      },
    })
    rows.value = data.items
    total.value = data.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : '用户列表加载失败'
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function turnPage(delta: number) {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  void load()
}

async function openAssign(user: AdminUser) {
  assignUser.value = user
  selectedRoleIds.value = user.roles.map((role) => role.id)
  error.value = ''
  try {
    const data = await request<PageResult<Role>>('/admin/roles', {
      params: { page: 1, page_size: 100, status: 1, sort: 'id:asc' },
    })
    roleOptions.value = data.items
    assignOpen.value = true
  } catch (err) {
    error.value = err instanceof Error ? err.message : '角色列表加载失败'
  }
}

async function saveAssign() {
  if (!assignUser.value) return
  assignBusy.value = true
  error.value = ''
  try {
    await request(`/admin/users/${assignUser.value.id}/roles`, {
      method: 'PUT',
      data: { role_ids: selectedRoleIds.value },
    })
    assignOpen.value = false
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '授权失败'
  } finally {
    assignBusy.value = false
  }
}

async function openAuthz(user: AdminUser) {
  authzUser.value = user
  authz.value = null
  error.value = ''
  try {
    authz.value = await request<UserAuthz>(`/admin/users/${user.id}/authz`)
    authzOpen.value = true
  } catch (err) {
    error.value = err instanceof Error ? err.message : '权限快照加载失败'
  }
}

onMounted(load)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>用户授权</h2>
        <p>为用户分配角色，变更后该用户 Redis 会话与权限缓存立即失效。</p>
      </div>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>

    <div class="toolbar">
      <input
        v-model="keyword"
        class="input"
        placeholder="搜索用户名 / 昵称 / 邮箱"
        @keyup.enter="search"
      />
      <select v-model="roleCode" class="input select" @change="search">
        <option value="">全部角色</option>
        <option value="ADMIN">ADMIN</option>
        <option value="OPERATOR">OPERATOR</option>
        <option value="USER">USER</option>
      </select>
      <select v-model="status" class="input select" @change="search">
        <option value="">全部状态</option>
        <option value="1">启用</option>
        <option value="0">禁用</option>
      </select>
      <select v-model="sort" class="input select" @change="search">
        <option value="id:desc">按 ID 倒序</option>
        <option value="username:asc">按用户名</option>
        <option value="last_login_at:desc">按最近登录</option>
      </select>
      <button class="btn" @click="search">查询</button>
      <span class="toolbar-meta">共 {{ total }} 条</span>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户名</th>
            <th>昵称</th>
            <th>邮箱</th>
            <th>角色</th>
            <th>状态</th>
            <th>最近登录</th>
            <th class="right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="empty">加载中…</td>
          </tr>
          <tr v-else-if="!rows.length">
            <td colspan="8" class="empty">暂无用户</td>
          </tr>
          <tr v-for="user in rows" :key="user.id">
            <td class="mono">{{ user.id }}</td>
            <td class="mono">{{ user.username || user.open_id }}</td>
            <td>{{ user.nickname || '-' }}</td>
            <td class="muted small">{{ user.email || '-' }}</td>
            <td>
              <span v-for="role in user.roles" :key="role.id" class="chip accent">
                {{ role.role_code }}
              </span>
              <span v-if="!user.roles.length" class="muted small">未分配</span>
            </td>
            <td>
              <span class="status-dot" :class="{ on: user.status === 1 }">
                {{ user.status === 1 ? '启用' : '禁用' }}
              </span>
            </td>
            <td class="muted small">{{ user.last_login_at?.replace('T', ' ') || '-' }}</td>
            <td class="right actions">
              <button
                v-if="hasPermission('rbac:user:grant')"
                class="link-btn"
                @click="openAssign(user)"
              >
                分配角色
              </button>
              <button
                v-if="hasPermission('rbac:user:list')"
                class="link-btn"
                @click="openAuthz(user)"
              >
                查看权限
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pager">
      <span class="muted small">第 {{ page }} / {{ totalPages }} 页</span>
      <div class="pager-actions">
        <button class="btn ghost" :disabled="page <= 1" @click="turnPage(-1)">上一页</button>
        <button class="btn ghost" :disabled="page >= totalPages" @click="turnPage(1)">下一页</button>
      </div>
    </div>

    <ModalDialog
      v-if="assignOpen && assignUser"
      :title="`分配角色 · ${assignUser.username || assignUser.open_id}`"
      subtitle="保存后该用户所有在线会话会被撤销，需要重新登录"
      @close="assignOpen = false"
    >
      <div class="checkbox-list">
        <label v-for="role in roleOptions" :key="role.id" class="checkbox-row">
          <input v-model="selectedRoleIds" type="checkbox" :value="role.id" />
          <span>{{ role.role_name }}</span>
          <code>{{ role.role_code }}</code>
        </label>
      </div>
      <template #footer>
        <button class="btn ghost" @click="assignOpen = false">取消</button>
        <button class="btn primary" :disabled="assignBusy" @click="saveAssign">
          {{ assignBusy ? '保存中…' : '保存角色' }}
        </button>
      </template>
    </ModalDialog>

    <ModalDialog
      v-if="authzOpen && authzUser"
      :title="`权限快照 · ${authzUser.username || authzUser.open_id}`"
      subtitle="数据来自 Redis 权限缓存，缓存未命中时会回源数据库并重建"
      wide
      @close="authzOpen = false"
    >
      <div v-if="authz" class="authz-grid">
        <section>
          <h4>角色</h4>
          <div class="chip-row">
            <span v-for="role in authz.roles" :key="role" class="chip accent">{{ role }}</span>
            <span v-if="!authz.roles.length" class="muted small">未分配角色</span>
          </div>
          <h4>菜单</h4>
          <ul class="menu-list">
            <li v-for="menu in authz.menus" :key="menu.id">
              {{ menu.menu_name }}
              <ul v-if="menu.children.length">
                <li v-for="child in menu.children" :key="child.id">{{ child.menu_name }}</li>
              </ul>
            </li>
          </ul>
        </section>
        <section>
          <h4>接口权限（{{ authz.permissions.length }}）</h4>
          <div class="chip-row">
            <code v-for="code in authz.permissions" :key="code" class="chip mono">{{ code }}</code>
            <span v-if="!authz.permissions.length" class="muted small">暂无权限</span>
          </div>
        </section>
      </div>
    </ModalDialog>
  </section>
</template>

<style scoped>
.checkbox-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
}

.checkbox-row code {
  font-size: 10.5px;
  color: var(--muted);
}

.authz-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.authz-grid h4 {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--ink);
}

.authz-grid h4 + h4 {
  margin-top: 18px;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.menu-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12.5px;
  color: var(--text);
}

.menu-list ul {
  margin: 4px 0 0;
  padding-left: 16px;
  color: var(--muted);
}

@media (max-width: 760px) {
  .authz-grid {
    grid-template-columns: 1fr;
  }
}
</style>
