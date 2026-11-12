<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import LoginView from './components/LoginView.vue'
import MenuIcon from './components/MenuIcon.vue'
import DashboardPage from './pages/DashboardPage.vue'
import MenusPage from './pages/MenusPage.vue'
import PermissionsPage from './pages/PermissionsPage.vue'
import RolesPage from './pages/RolesPage.vue'
import UsersPage from './pages/UsersPage.vue'
import type { MenuNode } from './api/types'
import { auth, logoutAccount, refreshMe, restoreSession } from './stores/auth'

const activePath = ref('/admin')
const toast = ref('')
const refreshing = ref(false)

interface MenuGroup {
  root: MenuNode
  children: MenuNode[]
}

const groups = computed<MenuGroup[]>(() =>
  (auth.me?.menus || []).map((root) => ({ root, children: root.children })),
)

const activeTitle = computed(() => {
  const found = findMenu(auth.me?.menus || [], activePath.value)
  return found?.menu_name || '控制台'
})

const sessionBadge = computed(() => {
  const me = auth.me
  if (!me) return ''
  return `${me.session.count} 个会话 · ${me.session.backend}`
})

function findMenu(menus: MenuNode[], path: string): MenuNode | null {
  for (const menu of menus) {
    if (menu.path === path) return menu
    const child = findMenu(menu.children, path)
    if (child) return child
  }
  return null
}

function pickDefaultPath(): string {
  const menus = auth.me?.menus || []
  const preferred = ['/admin', '/admin/roles', '/admin/menus', '/admin/permissions', '/admin/users']
  for (const path of preferred) {
    if (findMenu(menus, path)) return path
  }
  const firstLeaf = menus.find((menu) => !menu.children.length && menu.path)
  return firstLeaf?.path || (menus[0]?.path ?? '')
}

function navigate(path: string | null) {
  if (!path) return
  activePath.value = path
}

function showToast(message: string) {
  toast.value = message
  window.setTimeout(() => {
    if (toast.value === message) toast.value = ''
  }, 2600)
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await refreshMe()
    if (!findMenu(auth.me?.menus || [], activePath.value)) {
      activePath.value = pickDefaultPath()
    }
    showToast('权限快照已刷新')
  } catch (err) {
    showToast(err instanceof Error ? err.message : '刷新失败')
  } finally {
    refreshing.value = false
  }
}

async function handleLogout() {
  await logoutAccount()
}

onMounted(async () => {
  await restoreSession()
  if (auth.me) activePath.value = pickDefaultPath()
})
</script>

<template>
  <div v-if="auth.booting" class="boot">
    <div class="boot-mark">TP</div>
    <p>正在校验登录凭证…</p>
  </div>

  <LoginView v-else-if="!auth.me" />

  <div v-else class="console">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <aside class="console-side">
      <div class="console-brand">
        <div class="brand-dot">TP</div>
        <div>
          <span class="brand-name">旅行规划智能体</span>
          <span class="brand-sub">管理控制台</span>
        </div>
      </div>

      <nav class="side-nav">
        <template v-for="group in groups" :key="group.root.id">
          <div v-if="group.children.length" class="nav-group">
            <span class="nav-group-title">
              <MenuIcon :name="group.root.icon" />
              {{ group.root.menu_name }}
            </span>
            <button
              v-for="child in group.children"
              :key="child.id"
              type="button"
              class="nav-item child"
              :class="{ active: child.path === activePath }"
              @click="navigate(child.path)"
            >
              <MenuIcon :name="child.icon" />
              <span>{{ child.menu_name }}</span>
            </button>
          </div>
          <button
            v-else
            type="button"
            class="nav-item"
            :class="{ active: group.root.path === activePath }"
            @click="navigate(group.root.path)"
          >
            <MenuIcon :name="group.root.icon" />
            <span>{{ group.root.menu_name }}</span>
          </button>
        </template>
        <p v-if="!groups.length" class="nav-empty">当前账号未被授权任何菜单</p>
      </nav>

      <div class="side-foot">
        <span class="session-pill">{{ sessionBadge }}</span>
        <button type="button" class="ghost-btn" :disabled="refreshing" @click="handleRefresh">
          {{ refreshing ? '刷新中…' : '刷新权限' }}
        </button>
      </div>
    </aside>

    <main id="main-content" class="console-main">
      <header class="console-head">
        <div class="head-title">
          <h1>{{ activeTitle }}</h1>
          <span class="head-path">{{ activePath }}</span>
        </div>
        <div class="head-user">
          <div class="head-identity">
            <span class="head-name">{{ auth.me.user.nickname || auth.me.user.username }}</span>
            <span class="head-roles">
              <span v-for="role in auth.me.roles" :key="role" class="chip accent">{{ role }}</span>
              <span v-if="auth.me.is_admin" class="chip strong">超级管理员</span>
            </span>
          </div>
          <button type="button" class="logout-btn" @click="handleLogout">退出登录</button>
        </div>
      </header>

      <div class="console-body">
        <DashboardPage v-if="activePath === '/admin'" />
        <RolesPage v-else-if="activePath === '/admin/roles'" />
        <MenusPage v-else-if="activePath === '/admin/menus'" />
        <PermissionsPage v-else-if="activePath === '/admin/permissions'" />
        <UsersPage v-else-if="activePath === '/admin/users'" />
        <section v-else class="page placeholder">
          <h2>{{ activeTitle }}</h2>
          <p>
            该菜单属于 C 端功能，管理控制台仅负责账号、角色与权限治理。请前往旅行者端使用
            <code>{{ activePath }}</code>。
          </p>
        </section>
      </div>
    </main>

    <transition name="fade">
      <div v-if="toast" class="toast" role="status" aria-live="polite">{{ toast }}</div>
    </transition>
  </div>
</template>

<style scoped>
.boot {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--muted);
  font-size: 13px;
}

.boot-mark {
  width: 52px;
  height: 52px;
  border-radius: 15px;
  display: grid;
  place-items: center;
  font-weight: 800;
  color: #0b5d57;
  background: var(--accent-soft);
  box-shadow: inset 0 0 0 1px var(--line-strong);
}

.console {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 244px minmax(0, 1fr);
  background: var(--bg);
}

.skip-link {
  position: absolute;
  left: 12px;
  top: -48px;
  z-index: 100;
  padding: 8px 14px;
  border-radius: 8px;
  background: var(--ink);
  color: #fff;
  font-size: 13px;
  text-decoration: none;
  transition: top 0.15s ease;
}

.skip-link:focus-visible {
  top: 12px;
}

.console-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 14px 14px;
  background: var(--side);
  border-right: 1px solid var(--line);
}

.console-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px 8px;
}

.brand-dot {
  width: 36px;
  height: 36px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 800;
  color: #0b5d57;
  background: var(--accent-soft);
  box-shadow: inset 0 0 0 1px var(--line-strong);
  flex-shrink: 0;
}

.brand-name {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink);
}

.brand-sub {
  display: block;
  font-size: 11px;
  color: var(--muted);
}

.side-nav {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.nav-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px 4px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.4px;
  color: var(--muted);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--text);
  text-align: left;
  cursor: pointer;
}

.nav-item.child {
  margin-left: 8px;
  font-size: 12.5px;
}

.nav-item:hover {
  background: var(--panel);
}

.nav-item.active {
  background: var(--accent-soft);
  border-color: transparent;
  color: var(--accent-strong);
  font-weight: 600;
  box-shadow: inset 3px 0 0 var(--accent);
}

.nav-empty {
  padding: 10px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.6;
}

.side-foot {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.session-pill {
  font-size: 11px;
  color: var(--muted);
  padding: 4px 8px;
  border-radius: 8px;
  background: var(--panel-alt);
  text-align: center;
}

.ghost-btn {
  padding: 7px 10px;
  border-radius: 9px;
  border: 1px solid var(--line-strong);
  background: #fff;
  font: inherit;
  font-size: 12px;
  color: var(--accent-strong);
  cursor: pointer;
}

.ghost-btn:hover:not(:disabled) {
  background: var(--accent-soft);
}

.ghost-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.console-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.console-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 26px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(8px);
  position: sticky;
  top: 0;
  z-index: 5;
}

.head-title h1 {
  margin: 0;
  font-size: 18px;
  color: var(--ink);
}

.head-path {
  font-size: 11px;
  color: var(--muted);
}

.head-user {
  display: flex;
  align-items: center;
  gap: 16px;
}

.head-identity {
  text-align: right;
}

.head-name {
  display: block;
  font-size: 13px;
  color: var(--ink);
}

.head-roles {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
  margin-top: 3px;
}

.logout-btn {
  padding: 7px 12px;
  border-radius: 9px;
  border: 1px solid var(--line-strong);
  background: #fff;
  font: inherit;
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
}

.logout-btn:hover {
  color: #b91c1c;
  border-color: #fecaca;
  background: #fef2f2;
}

.console-body {
  flex: 1;
  padding: 22px 26px 34px;
  overflow-y: auto;
}

.placeholder {
  max-width: 640px;
}

.placeholder h2 {
  margin: 0 0 10px;
  font-size: 18px;
  color: var(--ink);
}

.placeholder p {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.8;
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 26px;
  transform: translateX(-50%);
  padding: 9px 16px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.9);
  color: #fff;
  font-size: 12.5px;
  z-index: 90;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 960px) {
  .console {
    grid-template-columns: 1fr;
  }

  .console-side {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
  }

  .side-nav {
    flex-direction: row;
    flex-wrap: wrap;
    overflow: visible;
  }

  .nav-group {
    flex-direction: row;
    align-items: center;
  }

  .nav-group-title {
    padding: 0 6px;
  }

  .nav-item.child {
    margin-left: 0;
  }

  .side-foot {
    border-top: none;
    padding-top: 0;
    flex-direction: row;
    align-items: center;
  }

  .console-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .head-identity {
    text-align: left;
  }

  .head-roles {
    justify-content: flex-start;
  }
}
</style>
