<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '../api/http'
import type { MenuItem, PageResult } from '../api/types'
import ModalDialog from '../components/ModalDialog.vue'
import MenuIcon from '../components/MenuIcon.vue'
import { hasPermission } from '../stores/auth'

const rows = ref<MenuItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const status = ref('')
const sort = ref('sort_no:asc')
const loading = ref(false)
const error = ref('')

const formOpen = ref(false)
const editing = ref<MenuItem | null>(null)
const parentOptions = ref<MenuItem[]>([])
const form = reactive({
  menu_code: '',
  menu_name: '',
  parent_id: '' as string | number,
  path: '',
  icon: '',
  sort_no: 0,
  status: 1,
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const parentNames = computed(() => {
  const map = new Map<number, string>()
  rows.value.forEach((menu) => map.set(menu.id, menu.menu_name))
  return map
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await request<PageResult<MenuItem>>('/admin/menus', {
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
    error.value = err instanceof Error ? err.message : '菜单列表加载失败'
  } finally {
    loading.value = false
  }
}

async function loadParents() {
  try {
    const data = await request<PageResult<MenuItem>>('/admin/menus', {
      params: { page: 1, page_size: 100, sort: 'sort_no:asc' },
    })
    parentOptions.value = data.items
  } catch {
    parentOptions.value = []
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

async function openCreate() {
  editing.value = null
  Object.assign(form, {
    menu_code: '',
    menu_name: '',
    parent_id: '',
    path: '',
    icon: '',
    sort_no: 0,
    status: 1,
  })
  await loadParents()
  formOpen.value = true
}

async function openEdit(menu: MenuItem) {
  editing.value = menu
  Object.assign(form, {
    menu_code: menu.menu_code,
    menu_name: menu.menu_name,
    parent_id: menu.parent_id ?? '',
    path: menu.path || '',
    icon: menu.icon || '',
    sort_no: menu.sort_no,
    status: menu.status,
  })
  await loadParents()
  formOpen.value = true
}

async function saveMenu() {
  if (!form.menu_name.trim()) {
    error.value = '请填写菜单名称'
    return
  }
  const payload = {
    menu_name: form.menu_name.trim(),
    parent_id: form.parent_id === '' ? null : Number(form.parent_id),
    path: form.path.trim() || null,
    icon: form.icon.trim() || null,
    sort_no: Number(form.sort_no) || 0,
    status: form.status,
  }
  try {
    if (editing.value) {
      await request(`/admin/menus/${editing.value.id}`, { method: 'PATCH', data: payload })
    } else {
      await request('/admin/menus', {
        method: 'POST',
        data: { ...payload, menu_code: form.menu_code.trim() },
      })
    }
    formOpen.value = false
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败'
  }
}

async function removeMenu(menu: MenuItem) {
  if (!window.confirm(`确认删除菜单「${menu.menu_name}」？`)) return
  try {
    await request(`/admin/menus/${menu.id}`, { method: 'DELETE' })
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除失败'
  }
}

onMounted(load)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>菜单管理</h2>
        <p>菜单是前端动态渲染的依据，需先在此定义再由角色授权。</p>
      </div>
      <button v-if="hasPermission('rbac:menu:create')" class="btn primary" @click="openCreate">
        新增菜单
      </button>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>

    <div class="toolbar">
      <input v-model="keyword" class="input" placeholder="搜索编码或名称" @keyup.enter="search" />
      <select v-model="status" class="input select" @change="search">
        <option value="">全部状态</option>
        <option value="1">启用</option>
        <option value="0">禁用</option>
      </select>
      <select v-model="sort" class="input select" @change="search">
        <option value="sort_no:asc">按排序号</option>
        <option value="id:asc">按 ID 升序</option>
      </select>
      <button class="btn" @click="search">查询</button>
      <span class="toolbar-meta">共 {{ total }} 条</span>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>菜单</th>
            <th>编码</th>
            <th>父级</th>
            <th>路由</th>
            <th>排序</th>
            <th>状态</th>
            <th class="right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="empty">加载中…</td>
          </tr>
          <tr v-else-if="!rows.length">
            <td colspan="8" class="empty">暂无菜单</td>
          </tr>
          <tr v-for="menu in rows" :key="menu.id">
            <td class="mono">{{ menu.id }}</td>
            <td>
              <span class="menu-cell">
                <MenuIcon :name="menu.icon" />
                {{ menu.menu_name }}
              </span>
            </td>
            <td><code class="chip mono">{{ menu.menu_code }}</code></td>
            <td class="muted">
              {{ menu.parent_id ? parentNames.get(menu.parent_id) || `#${menu.parent_id}` : '-' }}
            </td>
            <td class="mono small">{{ menu.path || '-' }}</td>
            <td class="mono">{{ menu.sort_no }}</td>
            <td>
              <span class="status-dot" :class="{ on: menu.status === 1 }">
                {{ menu.status === 1 ? '启用' : '禁用' }}
              </span>
            </td>
            <td class="right actions">
              <button
                v-if="hasPermission('rbac:menu:update')"
                class="link-btn"
                @click="openEdit(menu)"
              >
                编辑
              </button>
              <button
                v-if="hasPermission('rbac:menu:delete')"
                class="link-btn danger"
                @click="removeMenu(menu)"
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
      :title="editing ? '编辑菜单' : '新增菜单'"
      subtitle="菜单编码创建后不可修改"
      @close="formOpen = false"
    >
      <div class="form-stack">
        <label>
          菜单编码
          <input
            v-model="form.menu_code"
            class="input"
            :disabled="Boolean(editing)"
            placeholder="如 admin_roles"
          />
        </label>
        <label>
          菜单名称
          <input v-model="form.menu_name" class="input" placeholder="如 角色权限" />
        </label>
        <div class="form-row">
          <label>
            父级菜单
            <select v-model="form.parent_id" class="input select">
              <option value="">顶级菜单</option>
              <option
                v-for="menu in parentOptions"
                :key="menu.id"
                :value="menu.id"
                :disabled="editing?.id === menu.id"
              >
                {{ menu.menu_name }}
              </option>
            </select>
          </label>
          <label>
            图标
            <input v-model="form.icon" class="input" placeholder="chat / map / shield…" />
          </label>
        </div>
        <label>
          路由地址
          <input v-model="form.path" class="input" placeholder="/admin/roles" />
        </label>
        <div class="form-row">
          <label>
            排序号
            <input v-model.number="form.sort_no" class="input" type="number" min="0" />
          </label>
          <label>
            状态
            <select v-model.number="form.status" class="input select">
              <option :value="1">启用</option>
              <option :value="0">禁用</option>
            </select>
          </label>
        </div>
      </div>
      <template #footer>
        <button class="btn ghost" @click="formOpen = false">取消</button>
        <button class="btn primary" @click="saveMenu">保存</button>
      </template>
    </ModalDialog>
  </section>
</template>

<style scoped>
.menu-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--ink);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
</style>
