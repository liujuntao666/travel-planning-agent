<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '../api/http'
import type { PageResult, PermissionItem } from '../api/types'
import ModalDialog from '../components/ModalDialog.vue'
import { hasPermission } from '../stores/auth'

const rows = ref<PermissionItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const resource = ref('')
const status = ref('')
const sort = ref('id:asc')
const loading = ref(false)
const error = ref('')

const formOpen = ref(false)
const editing = ref<PermissionItem | null>(null)
const form = reactive({
  perm_code: '',
  perm_name: '',
  resource: '',
  method: '',
  api_path: '',
  description: '',
  status: 1,
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await request<PageResult<PermissionItem>>('/admin/permissions', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        keyword: keyword.value.trim(),
        resource: resource.value.trim(),
        status: status.value,
        sort: sort.value,
      },
    })
    rows.value = data.items
    total.value = data.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : '接口权限加载失败'
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
  Object.assign(form, {
    perm_code: '',
    perm_name: '',
    resource: '',
    method: '',
    api_path: '',
    description: '',
    status: 1,
  })
  formOpen.value = true
}

function openEdit(item: PermissionItem) {
  editing.value = item
  Object.assign(form, {
    perm_code: item.perm_code,
    perm_name: item.perm_name,
    resource: item.resource || '',
    method: item.method || '',
    api_path: item.api_path || '',
    description: item.description || '',
    status: item.status,
  })
  formOpen.value = true
}

async function savePermission() {
  if (!form.perm_name.trim()) {
    error.value = '请填写权限名称'
    return
  }
  const payload = {
    perm_name: form.perm_name.trim(),
    resource: form.resource.trim() || null,
    method: form.method.trim().toUpperCase() || null,
    api_path: form.api_path.trim() || null,
    description: form.description.trim() || null,
    status: form.status,
  }
  try {
    if (editing.value) {
      await request(`/admin/permissions/${editing.value.id}`, { method: 'PATCH', data: payload })
    } else {
      await request('/admin/permissions', {
        method: 'POST',
        data: { ...payload, perm_code: form.perm_code.trim() },
      })
    }
    formOpen.value = false
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败'
  }
}

async function removePermission(item: PermissionItem) {
  if (!window.confirm(`确认删除接口权限「${item.perm_name}」？`)) return
  try {
    await request(`/admin/permissions/${item.id}`, { method: 'DELETE' })
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
        <h2>接口权限</h2>
        <p>权限编码与后端依赖注入校验一一对应，控制接口资源的访问范围。</p>
      </div>
      <button
        v-if="hasPermission('rbac:permission:create')"
        class="btn primary"
        @click="openCreate"
      >
        新增权限
      </button>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>

    <div class="toolbar">
      <input v-model="keyword" class="input" placeholder="搜索编码 / 名称 / 路径" @keyup.enter="search" />
      <input v-model="resource" class="input" placeholder="资源分组，如 rbac" @keyup.enter="search" />
      <select v-model="status" class="input select" @change="search">
        <option value="">全部状态</option>
        <option value="1">启用</option>
        <option value="0">禁用</option>
      </select>
      <select v-model="sort" class="input select" @change="search">
        <option value="id:asc">按 ID 升序</option>
        <option value="perm_code:asc">按编码</option>
        <option value="resource:asc">按资源</option>
      </select>
      <button class="btn" @click="search">查询</button>
      <span class="toolbar-meta">共 {{ total }} 条</span>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>权限编码</th>
            <th>名称</th>
            <th>资源</th>
            <th>方法</th>
            <th>接口路径</th>
            <th>状态</th>
            <th class="right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="empty">加载中…</td>
          </tr>
          <tr v-else-if="!rows.length">
            <td colspan="8" class="empty">暂无接口权限</td>
          </tr>
          <tr v-for="item in rows" :key="item.id">
            <td class="mono">{{ item.id }}</td>
            <td><code class="chip mono">{{ item.perm_code }}</code></td>
            <td>{{ item.perm_name }}</td>
            <td class="muted">{{ item.resource || '-' }}</td>
            <td><span v-if="item.method" class="method-tag">{{ item.method }}</span><span v-else>-</span></td>
            <td class="mono small">{{ item.api_path || '-' }}</td>
            <td>
              <span class="status-dot" :class="{ on: item.status === 1 }">
                {{ item.status === 1 ? '启用' : '禁用' }}
              </span>
            </td>
            <td class="right actions">
              <button
                v-if="hasPermission('rbac:permission:update')"
                class="link-btn"
                @click="openEdit(item)"
              >
                编辑
              </button>
              <button
                v-if="hasPermission('rbac:permission:delete')"
                class="link-btn danger"
                @click="removePermission(item)"
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
      :title="editing ? '编辑接口权限' : '新增接口权限'"
      subtitle="权限编码创建后不可修改，建议与接口语义保持一致"
      @close="formOpen = false"
    >
      <div class="form-stack">
        <label>
          权限编码
          <input
            v-model="form.perm_code"
            class="input"
            :disabled="Boolean(editing)"
            placeholder="如 rbac:role:list"
          />
        </label>
        <label>
          权限名称
          <input v-model="form.perm_name" class="input" placeholder="如 角色列表" />
        </label>
        <div class="form-row">
          <label>
            资源分组
            <input v-model="form.resource" class="input" placeholder="rbac / trip / resource" />
          </label>
          <label>
            HTTP 方法
            <select v-model="form.method" class="input select">
              <option value="">不限</option>
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="PATCH">PATCH</option>
              <option value="DELETE">DELETE</option>
            </select>
          </label>
        </div>
        <label>
          接口路径
          <input v-model="form.api_path" class="input" placeholder="/api/v1/admin/roles" />
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
        <button class="btn primary" @click="savePermission">保存</button>
      </template>
    </ModalDialog>
  </section>
</template>

<style scoped>
.method-tag {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 5px;
  font-size: 10.5px;
  font-weight: 700;
  color: #0f766e;
  background: #ccfbf1;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
</style>
