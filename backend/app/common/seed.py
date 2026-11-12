"""RBAC 种子数据：角色、菜单、接口权限与演示账号。

在应用启动时幂等执行：仅补齐缺失记录，不覆盖已有配置。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.config import settings
from app.common.db import SessionLocal
from app.common.logging import get_logger
from app.common.security import hash_password
from app.models import Menu, Permission, Role, RoleMenu, RolePermission, User, UserRole

log = get_logger(__name__)

ROLES = [
    ("ADMIN", "超级管理员", "拥有全部菜单与接口权限"),
    ("OPERATOR", "运营管理员", "可查看运营日志与业务数据"),
    ("USER", "普通用户", "旅行规划与行程编辑"),
]

MENUS = [
    ("chat", "旅行规划", None, "/chat", "chat", 1),
    ("trips", "我的行程", None, "/trips", "map", 2),
    ("tips", "出行锦囊", None, "/tips", "book", 3),
    ("admin", "系统管理", None, "/admin", "shield", 9),
    ("admin_roles", "角色权限", "admin", "/admin/roles", "users", 1),
    ("admin_menus", "菜单管理", "admin", "/admin/menus", "menu", 2),
    ("admin_permissions", "接口权限", "admin", "/admin/permissions", "key", 3),
    ("admin_users", "用户授权", "admin", "/admin/users", "user", 4),
]

PERMISSIONS = [
    ("trip:read", "查看行程", "trip", "GET", "/api/v1/trips/{trip_id}"),
    ("trip:write", "编辑行程", "trip", "PATCH", "/api/v1/trips/{trip_id}/items/{item_id}"),
    ("conversation:read", "查看会话", "conversation", "GET", "/api/v1/conversations"),
    ("conversation:write", "发送消息", "conversation", "POST", "/api/v1/conversations/{id}/messages"),
    ("resource:read", "查询资源", "resource", "GET", "/api/v1/resources/pois"),
    ("export:create", "导出行程", "export", "POST", "/api/v1/trips/{trip_id}/exports"),
    ("system:log:read", "查看工具日志", "system", "GET", "/api/v1/tool-logs"),
    ("rbac:role:list", "角色列表", "rbac", "GET", "/api/v1/admin/roles"),
    ("rbac:role:create", "新增角色", "rbac", "POST", "/api/v1/admin/roles"),
    ("rbac:role:update", "修改角色", "rbac", "PATCH", "/api/v1/admin/roles/{id}"),
    ("rbac:role:delete", "删除角色", "rbac", "DELETE", "/api/v1/admin/roles/{id}"),
    ("rbac:role:grant", "角色授权", "rbac", "PUT", "/api/v1/admin/roles/{id}/menus"),
    ("rbac:menu:list", "菜单列表", "rbac", "GET", "/api/v1/admin/menus"),
    ("rbac:menu:create", "新增菜单", "rbac", "POST", "/api/v1/admin/menus"),
    ("rbac:menu:update", "修改菜单", "rbac", "PATCH", "/api/v1/admin/menus/{id}"),
    ("rbac:menu:delete", "删除菜单", "rbac", "DELETE", "/api/v1/admin/menus/{id}"),
    ("rbac:permission:list", "权限列表", "rbac", "GET", "/api/v1/admin/permissions"),
    ("rbac:permission:create", "新增权限", "rbac", "POST", "/api/v1/admin/permissions"),
    ("rbac:permission:update", "修改权限", "rbac", "PATCH", "/api/v1/admin/permissions/{id}"),
    ("rbac:permission:delete", "删除权限", "rbac", "DELETE", "/api/v1/admin/permissions/{id}"),
    ("rbac:user:list", "用户列表", "rbac", "GET", "/api/v1/admin/users"),
    ("rbac:user:grant", "用户授权", "rbac", "PUT", "/api/v1/admin/users/{id}/roles"),
]

USER_PERMISSIONS = [
    "trip:read",
    "trip:write",
    "conversation:read",
    "conversation:write",
    "resource:read",
    "export:create",
]

ROLE_MENUS = {
    "ADMIN": [code for code, *_ in MENUS],
    "OPERATOR": ["chat", "trips", "tips"],
    "USER": ["chat", "trips", "tips"],
}

ROLE_PERMISSIONS = {
    "ADMIN": [code for code, *_ in PERMISSIONS],
    "OPERATOR": USER_PERMISSIONS + ["system:log:read"],
    "USER": USER_PERMISSIONS,
}


def _get_or_create_role(db: Session, code: str, name: str, description: str) -> Role:
    role = db.scalar(select(Role).where(Role.role_code == code))
    if role:
        if role.deleted:
            role.deleted = 0
        return role
    role = Role(role_code=code, role_name=name, description=description, status=1)
    db.add(role)
    db.flush()
    return role


def _get_or_create_menu(db: Session, code: str, name: str, parent_id: int | None,
                        path: str | None, icon: str | None, sort_no: int) -> Menu:
    menu = db.scalar(select(Menu).where(Menu.menu_code == code))
    if menu:
        if menu.deleted:
            menu.deleted = 0
        return menu
    menu = Menu(menu_code=code, menu_name=name, parent_id=parent_id, path=path,
                icon=icon, sort_no=sort_no, status=1)
    db.add(menu)
    db.flush()
    return menu


def _get_or_create_permission(db: Session, code: str, name: str, resource: str,
                              method: str, api_path: str) -> Permission:
    permission = db.scalar(select(Permission).where(Permission.perm_code == code))
    if permission:
        if permission.deleted:
            permission.deleted = 0
        return permission
    permission = Permission(perm_code=code, perm_name=name, resource=resource,
                            method=method, api_path=api_path, status=1)
    db.add(permission)
    db.flush()
    return permission


def _link_role_menu(db: Session, role_id: int, menu_id: int) -> None:
    exists = db.scalar(
        select(RoleMenu).where(RoleMenu.role_id == role_id, RoleMenu.menu_id == menu_id)
    )
    if not exists:
        db.add(RoleMenu(role_id=role_id, menu_id=menu_id))


def _link_role_permission(db: Session, role_id: int, permission_id: int) -> None:
    exists = db.scalar(
        select(RolePermission).where(
            RolePermission.role_id == role_id, RolePermission.permission_id == permission_id
        )
    )
    if not exists:
        db.add(RolePermission(role_id=role_id, permission_id=permission_id))


def _link_user_role(db: Session, user_id: int, role_id: int) -> None:
    exists = db.scalar(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )
    if not exists:
        db.add(UserRole(user_id=user_id, role_id=role_id))


def _ensure_account(db: Session, username: str, password: str, nickname: str,
                    role_code: str, role_id: int) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if not user:
        user = User(
            open_id=f"acct:{username}",
            username=username,
            password_hash=hash_password(password),
            nickname=nickname,
            email=None,
            source="WEB",
            role=role_code,
            status=1,
        )
        db.add(user)
        db.flush()
    elif not user.password_hash:
        user.password_hash = hash_password(password)
    _link_user_role(db, user.id, role_id)
    return user


def seed_rbac() -> dict:
    if not settings.seed_rbac:
        return {"skipped": True}
    with SessionLocal() as db:
        roles = {code: _get_or_create_role(db, code, name, desc) for code, name, desc in ROLES}
        menus = {}
        for code, name, parent_code, path, icon, sort_no in MENUS:
            parent_id = menus[parent_code].id if parent_code else None
            menus[code] = _get_or_create_menu(db, code, name, parent_id, path, icon, sort_no)
        permissions = {
            code: _get_or_create_permission(db, code, name, resource, method, api_path)
            for code, name, resource, method, api_path in PERMISSIONS
        }

        for role_code, menu_codes in ROLE_MENUS.items():
            for menu_code in menu_codes:
                _link_role_menu(db, roles[role_code].id, menus[menu_code].id)
        for role_code, perm_codes in ROLE_PERMISSIONS.items():
            for perm_code in perm_codes:
                _link_role_permission(db, roles[role_code].id, permissions[perm_code].id)

        _ensure_account(
            db,
            settings.seed_admin_username,
            settings.seed_admin_password,
            "系统管理员",
            "ADMIN",
            roles["ADMIN"].id,
        )
        _ensure_account(
            db,
            settings.seed_demo_username,
            settings.seed_demo_password,
            "演示旅行者",
            "USER",
            roles["USER"].id,
        )
        db.commit()

    summary = {
        "roles": len(roles),
        "menus": len(menus),
        "permissions": len(permissions),
        "admin": settings.seed_admin_username,
        "demo": settings.seed_demo_username,
    }
    log.info("rbac_seeded %s", summary)
    return summary
