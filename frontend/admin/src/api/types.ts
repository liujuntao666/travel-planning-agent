export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface UserInfo {
  id: number
  username: string | null
  open_id: string
  nickname: string | null
  email: string | null
  phone: string | null
  avatar_url: string | null
  role: string
  status: number
  last_login_at: string | null
}

export interface MenuNode {
  id: number
  menu_code: string
  menu_name: string
  path: string | null
  icon: string | null
  children: MenuNode[]
}

export interface MePayload {
  user: UserInfo
  roles: string[]
  permissions: string[]
  menus: MenuNode[]
  is_admin: boolean
  session: { count: number; backend: string }
}

export interface LoginResult extends MePayload {
  access_token: string
  token_type: string
  expires_in: number
}

export interface Captcha {
  captcha_id: string
  image: string
  expires_in: number
  debug_code?: string
}

export interface Role {
  id: number
  role_code: string
  role_name: string
  description: string | null
  status: number
  created_at: string | null
}

export interface MenuItem {
  id: number
  menu_code: string
  menu_name: string
  parent_id: number | null
  path: string | null
  icon: string | null
  sort_no: number
  status: number
}

export interface PermissionItem {
  id: number
  perm_code: string
  perm_name: string
  resource: string | null
  method: string | null
  api_path: string | null
  description: string | null
  status: number
}

export interface AdminUser {
  id: number
  username: string | null
  open_id: string
  nickname: string | null
  email: string | null
  phone: string | null
  role: string
  status: number
  last_login_at: string | null
  roles: { id: number; role_code: string; role_name: string }[]
}

export interface RoleGrants {
  role_id: number
  menu_ids: number[]
  permission_ids: number[]
}

export interface UserAuthz {
  user_id: number
  username: string | null
  roles: string[]
  permissions: string[]
  menus: MenuNode[]
  is_admin: boolean
}

export interface Overview {
  roles: number
  menus: number
  permissions: number
  users: number
  redis_backend: string
}
