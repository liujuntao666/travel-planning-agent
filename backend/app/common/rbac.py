"""RBAC：角色、菜单、接口权限的读取与缓存。"""
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import get_current_user
from app.common.config import settings
from app.common.db import get_db
from app.common.errors import ForbiddenError
from app.common.redis_client import (
    cache_delete,
    cache_delete_pattern,
    cache_get_json,
    cache_set_json,
)
from app.models import Menu, Permission, Role, RoleMenu, RolePermission, User, UserRole

USER_AUTHZ_PREFIX = "rbac:user:"


def _role_codes(db: Session, user: User) -> list[str]:
    codes = list(
        db.scalars(
            select(Role.role_code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id, Role.deleted == 0, Role.status == 1)
        )
    )
    if not codes and user.role:
        codes = [user.role]
    return sorted(set(codes))


def _permission_codes(db: Session, role_ids: list[int], is_admin: bool) -> list[str]:
    if is_admin:
        return sorted(
            set(
                db.scalars(
                    select(Permission.perm_code).where(
                        Permission.deleted == 0, Permission.status == 1
                    )
                )
            )
        )
    if not role_ids:
        return []
    return sorted(
        set(
            db.scalars(
                select(Permission.perm_code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(
                    RolePermission.role_id.in_(role_ids),
                    Permission.deleted == 0,
                    Permission.status == 1,
                )
            )
        )
    )


def _menu_tree(db: Session, role_ids: list[int], is_admin: bool) -> list[dict]:
    if is_admin:
        rows = list(
            db.scalars(
                select(Menu).where(Menu.deleted == 0, Menu.status == 1).order_by(Menu.sort_no, Menu.id)
            )
        )
    elif role_ids:
        rows = list(
            db.scalars(
                select(Menu)
                .join(RoleMenu, RoleMenu.menu_id == Menu.id)
                .where(
                    RoleMenu.role_id.in_(role_ids),
                    Menu.deleted == 0,
                    Menu.status == 1,
                )
                .order_by(Menu.sort_no, Menu.id)
            )
        )
    else:
        rows = []

    nodes = {
        menu.id: {
            "id": menu.id,
            "menu_code": menu.menu_code,
            "menu_name": menu.menu_name,
            "path": menu.path,
            "icon": menu.icon,
            "children": [],
        }
        for menu in rows
    }
    roots: list[dict] = []
    for menu in rows:
        node = nodes[menu.id]
        if menu.parent_id and menu.parent_id in nodes:
            nodes[menu.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def load_user_authz(db: Session, user: User) -> dict:
    cache_key = f"{USER_AUTHZ_PREFIX}{user.id}"
    cached = cache_get_json(cache_key)
    if cached:
        return cached

    roles = _role_codes(db, user)
    role_ids = list(
        db.scalars(
            select(Role.id).where(Role.role_code.in_(roles), Role.deleted == 0, Role.status == 1)
        )
    )
    is_admin = "ADMIN" in roles or user.role == "ADMIN"
    payload = {
        "roles": roles,
        "permissions": _permission_codes(db, role_ids, is_admin),
        "menus": _menu_tree(db, role_ids, is_admin),
        "is_admin": is_admin,
    }
    cache_set_json(cache_key, payload, settings.authz_cache_ttl_s)
    return payload


def invalidate_user_authz(user_id: int) -> None:
    cache_delete(f"{USER_AUTHZ_PREFIX}{user_id}")


def invalidate_role_authz(db: Session, role_id: int) -> None:
    user_ids = list(db.scalars(select(UserRole.user_id).where(UserRole.role_id == role_id)))
    for user_id in set(user_ids):
        invalidate_user_authz(user_id)


def invalidate_all_authz() -> None:
    """菜单/权限定义变更后，所有用户的权限快照都需要重建。"""
    cache_delete_pattern(f"{USER_AUTHZ_PREFIX}*")


def has_permission(db: Session, user: User, code: str) -> bool:
    authz = load_user_authz(db, user)
    return authz.get("is_admin") or code in authz.get("permissions", [])


def require_permission(code: str):
    """接口级权限校验，等价于 Spring Security 的 @PreAuthorize。"""

    def dependency(
        current: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        if not has_permission(db, current, code):
            raise ForbiddenError(f"缺少接口权限：{code}")
        return current

    return dependency
