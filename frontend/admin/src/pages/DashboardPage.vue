<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '../api/http'
import type { Overview } from '../api/types'
import MenuIcon from '../components/MenuIcon.vue'
import { auth } from '../stores/auth'

const overview = ref<Overview | null>(null)
const error = ref('')

const canSeeOverview = computed(() => Boolean(auth.me?.is_admin))

const stats = computed(() => {
  const data = overview.value
  return [
    { label: '角色', value: data?.roles ?? '-', hint: 'RBAC 角色定义' },
    { label: '菜单', value: data?.menus ?? '-', hint: '动态菜单来源' },
    { label: '接口权限', value: data?.permissions ?? '-', hint: '接口级鉴权粒度' },
    { label: '账号', value: data?.users ?? '-', hint: '已注册用户' },
  ]
})

const permissionGroups = computed(() => {
  const groups = new Map<string, string[]>()
  for (const code of auth.me?.permissions || []) {
    const resource = code.includes(':') ? code.split(':')[0] : 'other'
    groups.set(resource, [...(groups.get(resource) || []), code])
  }
  return [...groups.entries()].map(([resource, codes]) => ({ resource, codes }))
})

async function loadOverview() {
  if (!canSeeOverview.value) return
  try {
    overview.value = await request<Overview>('/admin/overview')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '概览加载失败'
  }
}

onMounted(loadOverview)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>工作台</h2>
        <p>当前登录身份、权限快照与会话状态均来自 Redis 中的登录凭证。</p>
      </div>
      <span class="status-pill" :class="{ ok: auth.me?.session.backend === 'redis' }">
        Redis 后端：{{ auth.me?.session.backend || '-' }}
      </span>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>

    <div v-if="canSeeOverview" class="stat-grid">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
        <span class="stat-hint">{{ item.hint }}</span>
      </article>
    </div>

    <div class="dash-grid">
      <article class="card">
        <h3>登录身份</h3>
        <dl class="kv">
          <dt>用户名</dt>
          <dd>{{ auth.me?.user.username || auth.me?.user.open_id }}</dd>
          <dt>昵称</dt>
          <dd>{{ auth.me?.user.nickname || '-' }}</dd>
          <dt>角色</dt>
          <dd>
            <span v-for="role in auth.me?.roles" :key="role" class="chip accent">{{ role }}</span>
            <span v-if="!auth.me?.roles.length" class="muted">未分配角色</span>
          </dd>
          <dt>超级管理员</dt>
          <dd>{{ auth.me?.is_admin ? '是' : '否' }}</dd>
          <dt>在线会话</dt>
          <dd>{{ auth.me?.session.count ?? 0 }} 个（同一账号多端登录）</dd>
        </dl>
      </article>

      <article class="card">
        <h3>动态菜单</h3>
        <p class="muted small">菜单按角色授权实时下发，无权限的菜单不会出现在导航中。</p>
        <ul class="menu-preview">
          <li v-for="menu in auth.me?.menus" :key="menu.id">
            <span class="menu-preview-row">
              <MenuIcon :name="menu.icon" />
              <span>{{ menu.menu_name }}</span>
              <code>{{ menu.path }}</code>
            </span>
            <ul v-if="menu.children.length" class="menu-children">
              <li v-for="child in menu.children" :key="child.id">
                <span>{{ child.menu_name }}</span>
                <code>{{ child.path }}</code>
              </li>
            </ul>
          </li>
        </ul>
      </article>
    </div>

    <article class="card">
      <h3>接口权限快照</h3>
      <p class="muted small">登录时写入 Redis，管理员变更角色授权后缓存自动失效并重建。</p>
      <div v-if="permissionGroups.length" class="permission-groups">
        <div v-for="group in permissionGroups" :key="group.resource" class="permission-group">
          <span class="permission-resource">{{ group.resource }}</span>
          <div class="permission-codes">
            <code v-for="code in group.codes" :key="code" class="chip mono">{{ code }}</code>
          </div>
        </div>
      </div>
      <p v-else class="muted">当前账号暂无接口权限，请联系管理员在「用户授权」中配置角色。</p>
    </article>
  </section>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 18px 20px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
}

.stat-label {
  font-size: 12px;
  color: var(--muted);
}

.stat-value {
  font-size: 28px;
  line-height: 1.1;
  color: var(--ink);
}

.stat-hint {
  font-size: 11.5px;
  color: var(--muted);
}

.dash-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
}

.kv {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 10px 12px;
  margin: 12px 0 0;
  font-size: 13px;
}

.kv dt {
  color: var(--muted);
}

.kv dd {
  margin: 0;
  color: var(--ink);
}

.menu-preview {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
}

.menu-preview-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink);
}

.menu-preview code {
  font-size: 11px;
  color: var(--muted);
  background: var(--panel-alt);
  padding: 1px 6px;
  border-radius: 5px;
}

.menu-children {
  margin: 6px 0 0 26px;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12.5px;
  color: var(--muted);
}

.menu-children li {
  display: flex;
  align-items: center;
  gap: 8px;
}

.permission-groups {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.permission-group {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 12px;
  align-items: start;
}

.permission-resource {
  font-size: 12px;
  color: var(--accent-strong);
  font-weight: 600;
}

.permission-codes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

@media (max-width: 1080px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dash-grid {
    grid-template-columns: 1fr;
  }
}
</style>
