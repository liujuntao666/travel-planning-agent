<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '../api/http'
import type { MenuItem, PageResult, PermissionItem, Role, RoleGrants } from '../api/types'
import ModalDialog from '../components/ModalDialog.vue'
import { hasPermission } from '../stores/auth'

const rows = ref<Role[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const status = ref<string>('')
const sort = ref('id:asc')
const loading = ref(false)
const error = ref('')

const formOpen = ref(false)
const editing = ref<Role | null>(null)
const form = reactive({ role_code: '', role_name: '', description: '', status: 1 })

const grantOpen = ref(false)
const grantRole = ref<Role | null>(null)
const allMenus = ref<MenuItem[]>([])
const allPermissions = ref<PermissionItem[]>([])
const selectedMenuIds = ref<number[]>([])
const selectedPermissionIds = ref<number[]>([])
const grantBusy = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const menuGroups = computed(() => {
  const roots = allMenus.value.filter((menu) => !menu.parent_id)
  return roots.map((root) => ({
    root,
    children: allMenus.value.filter((menu) => menu.parent_id === root.id),
  }))
})

const permissionGroups = computed(() => {
  const groups = new Map<string, PermissionItem[]>()
  for (const item of allPermissions.value) {
    const key = item.resource || 'other'
    groups.set(key, [...(groups.get(key) || []), item])
  }
  return [...groups.entries()].map(([resource, items]) => ({ resource, items }))
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await request<PageResult<Role>>('/admin/roles', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        keyword: keyword.value.trim(),
        status: status.value,
        sort: sort.value,
      },
    })
    rows.value = data.items
    total.value = data.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : '角色列表加载失败'
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

function openCreate() {
  editing.value = null
  form.role_code = ''
  form.role_name = ''
  form.description = ''
  form.status = 1
  formOpen.value = true
}

function openEdit(role: Role) {
  editing.value = role
  form.role_code = role.role_code
  form.role_name = role.role_name
  form.description = role.description || ''
  form.status = role.status
  formOpen.value = true
}

async function saveRole() {
  if (!form.role_name.trim()) {
    error.value = '请填写角色名称'
    return
  }
  try {
    if (editing.value) {
      await request(`/admin/roles/${editing.value.id}`, {
        method: 'PATCH',
        data: {
          role_name: form.role_name.trim(),
          description: form.description.trim() || null,
          status: form.status,
        },
      })
    } else {
      await request('/admin/roles', {
        method: 'POST',
        data: {
          role_code: form.role_code.trim().toUpperCase(),
          role_name: form.role_name.trim(),
          description: form.description.trim() || null,
          status: form.status,
        },
      })
    }
    formOpen.value = false
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败'
  }
}

async function removeRole(role: Role) {
  if (!window.confirm(`确认删除角色「${role.role_name}」？关联授权将一并解除。`)) return
  try {
    await request(`/admin/roles/${role.id}`, { method: 'DELETE' })
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除失败'
  }
}

async function openGrant(role: Role) {
  grantRole.value = role
  grantBusy.value = true
  error.value = ''
  try {
    const [grants, menus, permissions] = await Promise.all([
      request<RoleGrants>(`/admin/roles/${role.id}/grants`),
      request<PageResult<MenuItem>>('/admin/menus', { params: { page: 1, page_size: 100 } }),
      request<PageResult<PermissionItem>>('/admin/permissions', {
        params: { page: 1, page_size: 100 },
      }),
    ])
    selectedMenuIds.value = grants.menu_ids
    selectedPermissionIds.value = grants.permission_ids
    allMenus.value = menus.items
    allPermissions.value = permissions.items
    grantOpen.value = true
  } catch (err) {
    error.value = err instanceof Error ? err.message : '授权信息加载失败'
  } finally {
    grantBusy.value = false
  }
}

async function saveGrants() {
  if (!grantRole.value) return
  grantBusy.value = true
  error.value = ''
  try {
    await request(`/admin/roles/${grantRole.value.id}/menus`, {
      method: 'PUT',
      data: { menu_ids: selectedMenuIds.value },
    })
    await request(`/admin/roles/${grantRole.value.id}/permissions`, {
      method: 'PUT',
      data: { permission_ids: selectedPermissionIds.value },
    })
    grantOpen.value = false
  } catch (err) {
    error.value = err instanceof Error ? err.message : '授权保存失败'
  } finally {
    grantBusy.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>角色权限</h2>
        <p>角色是菜单与接口权限的载体，授权变更后对应权限缓存立即失效。</p>
      </div>
      <button v-if="hasPermission('rbac:role:create')" class="btn primary" @click="openCreate">
        新增角色
      </button>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>

    <div class="toolbar">
      <input
        v-model="keyword"
        class="input"
        placeholder="搜索角色编码或名称"
        @keyup.enter="search"
      />
      <select v-model="status" class="input select" @change="search">
        <option value="">全部状态</option>
        <option value="1">启用</option>
        <option value="0">禁用</option>
      </select>
      <select v-model="sort" class="input select" @change="search">
        <option value="id:asc">按 ID 升序</option>
        <option value="role_code:asc">按编码</option>
        <option value="created_at:desc">按创建时间</option>
      </select>
      <button class="btn" @click="search">查询</button>
      <span class="toolbar-meta">共 {{ total }} 条</span>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>角色编码</th>
            <th>角色名称</th>
            <th>描述</th>
            <th>状态</th>
            <th>创建时间</th>
            <th class="right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7" class="empty">加载中…</td>
          </tr>
          <tr v-else-if="!rows.length">
            <td colspan="7" class="empty">暂无角色</td>
          </tr>
          <tr v-for="role in rows" :key="role.id">
            <td class="mono">{{ role.id }}</td>
            <td><code class="chip mono">{{ role.role_code }}</code></td>
            <td>{{ role.role_name }}</td>
            <td class="muted">{{ role.description || '-' }}</td>
            <td>
              <span class="status-dot" :class="{ on: role.status === 1 }">
                {{ role.status === 1 ? '启用' : '禁用' }}
              </span>
            </td>
            <td class="muted small">{{ role.created_at?.replace('T', ' ') || '-' }}</td>
            <td class="right actions">
              <button
                v-if="hasPermission('rbac:role:grant')"
                class="link-btn"
                :disabled="grantBusy"
                @click="openGrant(role)"
              >
                授权
              </button>
              <button
                v-if="hasPermission('rbac:role:update')"
                class="link-btn"
                @click="openEdit(role)"
              >
                编辑
              </button>
              <button
                v-if="hasPermission('rbac:role:delete')"
                class="link-btn danger"
                @click="removeRole(role)"
              >
                删除
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
      v-if="formOpen"
      :title="editing ? '编辑角色' : '新增角色'"
      subtitle="角色编码创建后不可修改，内置 ADMIN / USER 角色受保护"
      @close="formOpen = false"
    >
      <div class="form-stack">
        <label>
          角色编码
          <input
            v-model="form.role_code"
            class="input"
            :disabled="Boolean(editing)"
            placeholder="如 OPERATOR"
          />
        </label>
        <label>
          角色名称
          <input v-model="form.role_name" class="input" placeholder="如 运营管理员" />
        </label>
        <label>
          描述
          <textarea v-model="form.description" class="input textarea" rows="3" />
        </label>
        <label>
          状态
          <select v-model.number="form.status" class="input select">
            <option :value="1">启用</option>
            <option :value="0">禁用</option>
          </select>
        </label>
      </div>
      <template #footer>
        <button class="btn ghost" @click="formOpen = false">取消</button>
        <button class="btn primary" @click="saveRole">保存</button>
      </template>
    </ModalDialog>

    <ModalDialog
      v-if="grantOpen && grantRole"
      :title="`授权 · ${grantRole.role_name}`"
      subtitle="勾选菜单控制前端动态菜单，勾选接口权限控制后端资源访问"
      wide
      @close="grantOpen = false"
    >
      <div class="grant-grid">
        <section>
          <h4>菜单权限</h4>
          <div class="checkbox-list">
            <div v-for="group in menuGroups" :key="group.root.id" class="checkbox-group">
              <label class="checkbox-row strong">
                <input v-model="selectedMenuIds" type="checkbox" :value="group.root.id" />
                {{ group.root.menu_name }}
                <code>{{ group.root.menu_code }}</code>
              </label>
              <label
                v-for="child in group.children"
                :key="child.id"
                class="checkbox-row indent"
              >
                <input v-model="selectedMenuIds" type="checkbox" :value="child.id" />
                {{ child.menu_name }}
                <code>{{ child.menu_code }}</code>
              </label>
            </div>
          </div>
        </section>
        <section>
          <h4>接口权限</h4>
          <div class="checkbox-list">
            <div
              v-for="group in permissionGroups"
              :key="group.resource"
              class="checkbox-group"
            >
              <span class="group-title">{{ group.resource }}</span>
              <label v-for="item in group.items" :key="item.id" class="checkbox-row">
                <input v-model="selectedPermissionIds" type="checkbox" :value="item.id" />
                {{ item.perm_name }}
                <code>{{ item.perm_code }}</code>
              </label>
            </div>
          </div>
        </section>
      </div>
      <template #footer>
        <button class="btn ghost" @click="grantOpen = false">取消</button>
        <button class="btn primary" :disabled="grantBusy" @click="saveGrants">
          {{ grantBusy ? '保存中…' : '保存授权' }}
        </button>
      </template>
    </ModalDialog>
  </section>
</template>

<style scoped>
.grant-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 22px;
}

.grant-grid h4 {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--ink);
}

.checkbox-list {
  max-height: 360px;
  overflow-y: auto;
  padding-right: 6px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.group-title {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--accent-strong);
  text-transform: uppercase;
  letter-spacing: 0.6px;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--text);
  cursor: pointer;
}

.checkbox-row.strong {
  color: var(--ink);
  font-weight: 600;
}

.checkbox-row.indent {
  padding-left: 22px;
}

.checkbox-row code {
  font-size: 10.5px;
  color: var(--muted);
}

@media (max-width: 760px) {
  .grant-grid {
    grid-template-columns: 1fr;
  }
}
</style>
