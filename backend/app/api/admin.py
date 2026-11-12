"""后台 RBAC 管理：角色、菜单、接口权限、角色授权与用户角色分配。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.common.auth import get_current_user
from app.common.auth_session import revoke_user_sessions
from app.common.db import get_db
from app.common.errors import ConflictError, NotFoundError, ValidationError
from app.common.pagination import PageParams, paginate
from app.common.ratelimit import TooManyRequestsError  # noqa: F401
from app.common.rbac import (
    invalidate_all_authz,
    invalidate_role_authz,
    invalidate_user_authz,
    load_user_authz,
    require_permission,
)
from app.common.redis_client import redis_backend
from app.models import Menu, Permission, Role, RoleMenu, RolePermission, User, UserRole
from app.schemas.admin import (
    MenuCreateIn,
    MenuIdsIn,
    MenuUpdateIn,
    PermissionCreateIn,
    PermissionIdsIn,
    PermissionUpdateIn,
    RoleCreateIn,
    RoleIdsIn,
    RoleUpdateIn,
)

router = APIRouter(prefix="/admin", tags=["admin"])

PROTECTED_ROLE_CODES = {"ADMIN", "USER"}


def _role_dict(role: Role) -> dict:
    return {
        "id": role.id,
        "role_code": role.role_code,
        "role_name": role.role_name,
        "description": role.description,
        "status": role.status,
        "created_at": role.created_at.isoformat() if role.created_at else None,
    }


def _menu_dict(menu: Menu) -> dict:
    return {
        "id": menu.id,
        "menu_code": menu.menu_code,
        "menu_name": menu.menu_name,
        "parent_id": menu.parent_id,
        "path": menu.path,
        "icon": menu.icon,
        "sort_no": menu.sort_no,
        "status": menu.status,
    }


def _permission_dict(permission: Permission) -> dict:
    return {
        "id": permission.id,
        "perm_code": permission.perm_code,
        "perm_name": permission.perm_name,
        "resource": permission.resource,
        "method": permission.method,
        "api_path": permission.api_path,
        "description": permission.description,
        "status": permission.status,
    }


def _user_roles(db: Session, user_id: int) -> list[dict]:
    rows = db.execute(
        select(Role.id, Role.role_code, Role.role_name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, Role.deleted == 0)
        .order_by(Role.id)
    ).all()
    return [{"id": r.id, "role_code": r.role_code, "role_name": r.role_name} for r in rows]


def _user_dict(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "open_id": user.open_id,
        "nickname": user.nickname,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "status": user.status,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "roles": _user_roles(db, user.id),
    }


def _get_role(db: Session, role_id: int) -> Role:
    role = db.scalar(select(Role).where(Role.id == role_id, Role.deleted == 0))
    if not role:
        raise NotFoundError("角色不存在")
    return role


def _get_menu(db: Session, menu_id: int) -> Menu:
    menu = db.scalar(select(Menu).where(Menu.id == menu_id, Menu.deleted == 0))
    if not menu:
        raise NotFoundError("菜单不存在")
    return menu


def _get_permission(db: Session, permission_id: int) -> Permission:
    permission = db.scalar(
        select(Permission).where(Permission.id == permission_id, Permission.deleted == 0)
    )
    if not permission:
        raise NotFoundError("接口权限不存在")
    return permission


@router.get("/overview", dependencies=[Depends(require_permission("rbac:role:list"))])
def overview(db: Session = Depends(get_db)) -> dict:
    return {
        "roles": db.scalar(select(func.count()).select_from(Role).where(Role.deleted == 0)) or 0,
        "menus": db.scalar(select(func.count()).select_from(Menu).where(Menu.deleted == 0)) or 0,
        "permissions": db.scalar(
            select(func.count()).select_from(Permission).where(Permission.deleted == 0)
        ) or 0,
        "users": db.scalar(select(func.count()).select_from(User).where(User.deleted == 0)) or 0,
        "redis_backend": redis_backend(),
    }


# ------------------------------------------------------------------ 角色
@router.get("/roles", dependencies=[Depends(require_permission("rbac:role:list"))])
def list_roles(
    keyword: str | None = Query(None, max_length=64),
    status: int | None = Query(None, ge=0, le=1),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Role).where(Role.deleted == 0)
    if keyword:
        stmt = stmt.where(or_(Role.role_code.contains(keyword), Role.role_name.contains(keyword)))
    if status is not None:
        stmt = stmt.where(Role.status == status)
    page = paginate(
        db, stmt, page_params,
        allowed_sort={"id": Role.id, "role_code": Role.role_code,
                      "role_name": Role.role_name, "created_at": Role.created_at},
        default_sort="id:asc",
    )
    page["items"] = [_role_dict(r) for r in page["items"]]
    return page


@router.post("/roles", dependencies=[Depends(require_permission("rbac:role:create"))])
def create_role(payload: RoleCreateIn, db: Session = Depends(get_db)) -> dict:
    exists = db.scalar(select(Role).where(Role.role_code == payload.role_code))
    if exists:
        raise ConflictError("角色编码已存在")
    role = Role(
        role_code=payload.role_code,
        role_name=payload.role_name,
        description=payload.description,
        status=payload.status,
    )
    db.add(role)
    db.commit()
    return _role_dict(role)


@router.patch("/roles/{role_id}", dependencies=[Depends(require_permission("rbac:role:update"))])
def update_role(role_id: int, payload: RoleUpdateIn, db: Session = Depends(get_db)) -> dict:
    role = _get_role(db, role_id)
    if role.role_code == "ADMIN" and payload.status == 0:
        raise ValidationError("超级管理员角色不能被禁用")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    db.commit()
    invalidate_role_authz(db, role.id)
    return _role_dict(role)


@router.delete("/roles/{role_id}", dependencies=[Depends(require_permission("rbac:role:delete"))])
def delete_role(role_id: int, db: Session = Depends(get_db)) -> dict:
    role = _get_role(db, role_id)
    if role.role_code in PROTECTED_ROLE_CODES:
        raise ValidationError(f"内置角色 {role.role_code} 不允许删除")
    invalidate_role_authz(db, role.id)
    db.query(RoleMenu).filter(RoleMenu.role_id == role.id).delete(synchronize_session=False)
    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete(
        synchronize_session=False
    )
    db.query(UserRole).filter(UserRole.role_id == role.id).delete(synchronize_session=False)
    # 同步清理用户表上的旧角色字段，避免权限快照回退到已删除角色
    db.query(User).filter(User.role == role.role_code).update(
        {User.role: "USER"}, synchronize_session=False
    )
    role.deleted = 1
    db.commit()
    return {"id": role_id, "deleted": True}


@router.get("/roles/{role_id}/grants",
            dependencies=[Depends(require_permission("rbac:role:list"))])
def role_grants(role_id: int, db: Session = Depends(get_db)) -> dict:
    _get_role(db, role_id)
    menu_ids = list(db.scalars(select(RoleMenu.menu_id).where(RoleMenu.role_id == role_id)))
    permission_ids = list(
        db.scalars(select(RolePermission.permission_id).where(RolePermission.role_id == role_id))
    )
    return {"role_id": role_id, "menu_ids": menu_ids, "permission_ids": permission_ids}


@router.put("/roles/{role_id}/menus",
            dependencies=[Depends(require_permission("rbac:role:grant"))])
def grant_menus(role_id: int, payload: MenuIdsIn, db: Session = Depends(get_db)) -> dict:
    role = _get_role(db, role_id)
    if payload.menu_ids:
        valid_ids = set(
            db.scalars(
                select(Menu.id).where(Menu.id.in_(payload.menu_ids), Menu.deleted == 0)
            )
        )
        missing = set(payload.menu_ids) - valid_ids
        if missing:
            raise ValidationError(f"菜单不存在：{sorted(missing)}")
    db.query(RoleMenu).filter(RoleMenu.role_id == role_id).delete(synchronize_session=False)
    for menu_id in sorted(set(payload.menu_ids)):
        db.add(RoleMenu(role_id=role_id, menu_id=menu_id))
    db.commit()
    invalidate_role_authz(db, role.id)
    return {"role_id": role_id, "menu_ids": sorted(set(payload.menu_ids))}


@router.put("/roles/{role_id}/permissions",
            dependencies=[Depends(require_permission("rbac:role:grant"))])
def grant_permissions(
    role_id: int, payload: PermissionIdsIn, db: Session = Depends(get_db)
) -> dict:
    role = _get_role(db, role_id)
    if payload.permission_ids:
        valid_ids = set(
            db.scalars(
                select(Permission.id).where(
                    Permission.id.in_(payload.permission_ids), Permission.deleted == 0
                )
            )
        )
        missing = set(payload.permission_ids) - valid_ids
        if missing:
            raise ValidationError(f"接口权限不存在：{sorted(missing)}")
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete(
        synchronize_session=False
    )
    for permission_id in sorted(set(payload.permission_ids)):
        db.add(RolePermission(role_id=role_id, permission_id=permission_id))
    db.commit()
    invalidate_role_authz(db, role.id)
    return {"role_id": role_id, "permission_ids": sorted(set(payload.permission_ids))}


# ------------------------------------------------------------------ 菜单
@router.get("/menus", dependencies=[Depends(require_permission("rbac:menu:list"))])
def list_menus(
    keyword: str | None = Query(None, max_length=64),
    parent_id: int | None = Query(None, ge=1),
    status: int | None = Query(None, ge=0, le=1),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Menu).where(Menu.deleted == 0)
    if keyword:
        stmt = stmt.where(or_(Menu.menu_code.contains(keyword), Menu.menu_name.contains(keyword)))
    if parent_id is not None:
        stmt = stmt.where(Menu.parent_id == parent_id)
    if status is not None:
        stmt = stmt.where(Menu.status == status)
    page = paginate(
        db, stmt, page_params,
        allowed_sort={"id": Menu.id, "menu_code": Menu.menu_code,
                      "sort_no": Menu.sort_no, "created_at": Menu.created_at},
        default_sort="sort_no:asc",
    )
    page["items"] = [_menu_dict(m) for m in page["items"]]
    return page


@router.post("/menus", dependencies=[Depends(require_permission("rbac:menu:create"))])
def create_menu(payload: MenuCreateIn, db: Session = Depends(get_db)) -> dict:
    exists = db.scalar(select(Menu).where(Menu.menu_code == payload.menu_code))
    if exists:
        raise ConflictError("菜单编码已存在")
    if payload.parent_id is not None:
        _get_menu(db, payload.parent_id)
    menu = Menu(**payload.model_dump())
    db.add(menu)
    db.commit()
    invalidate_all_authz()
    return _menu_dict(menu)


@router.patch("/menus/{menu_id}", dependencies=[Depends(require_permission("rbac:menu:update"))])
def update_menu(menu_id: int, payload: MenuUpdateIn, db: Session = Depends(get_db)) -> dict:
    menu = _get_menu(db, menu_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("parent_id") is not None:
        if data["parent_id"] == menu_id:
            raise ValidationError("菜单不能以自身作为父级")
        _get_menu(db, data["parent_id"])
    for field, value in data.items():
        setattr(menu, field, value)
    db.commit()
    invalidate_all_authz()
    return _menu_dict(menu)


@router.delete("/menus/{menu_id}",
               dependencies=[Depends(require_permission("rbac:menu:delete"))])
def delete_menu(menu_id: int, db: Session = Depends(get_db)) -> dict:
    menu = _get_menu(db, menu_id)
    child = db.scalar(select(Menu).where(Menu.parent_id == menu_id, Menu.deleted == 0))
    if child:
        raise ConflictError("请先删除子菜单")
    db.query(RoleMenu).filter(RoleMenu.menu_id == menu_id).delete(synchronize_session=False)
    menu.deleted = 1
    db.commit()
    invalidate_all_authz()
    return {"id": menu_id, "deleted": True}


# ------------------------------------------------------------------ 接口权限
@router.get("/permissions",
            dependencies=[Depends(require_permission("rbac:permission:list"))])
def list_permissions(
    keyword: str | None = Query(None, max_length=64),
    resource: str | None = Query(None, max_length=64),
    status: int | None = Query(None, ge=0, le=1),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Permission).where(Permission.deleted == 0)
    if keyword:
        stmt = stmt.where(or_(
            Permission.perm_code.contains(keyword),
            Permission.perm_name.contains(keyword),
            Permission.api_path.contains(keyword),
        ))
    if resource:
        stmt = stmt.where(Permission.resource == resource)
    if status is not None:
        stmt = stmt.where(Permission.status == status)
    page = paginate(
        db, stmt, page_params,
        allowed_sort={"id": Permission.id, "perm_code": Permission.perm_code,
                      "resource": Permission.resource, "created_at": Permission.created_at},
        default_sort="id:asc",
    )
    page["items"] = [_permission_dict(p) for p in page["items"]]
    return page


@router.post("/permissions",
             dependencies=[Depends(require_permission("rbac:permission:create"))])
def create_permission(payload: PermissionCreateIn, db: Session = Depends(get_db)) -> dict:
    exists = db.scalar(select(Permission).where(Permission.perm_code == payload.perm_code))
    if exists:
        raise ConflictError("权限编码已存在")
    permission = Permission(**payload.model_dump())
    db.add(permission)
    db.commit()
    invalidate_all_authz()
    return _permission_dict(permission)


@router.patch("/permissions/{permission_id}",
              dependencies=[Depends(require_permission("rbac:permission:update"))])
def update_permission(
    permission_id: int, payload: PermissionUpdateIn, db: Session = Depends(get_db)
) -> dict:
    permission = _get_permission(db, permission_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(permission, field, value)
    db.commit()
    invalidate_all_authz()
    return _permission_dict(permission)


@router.delete("/permissions/{permission_id}",
               dependencies=[Depends(require_permission("rbac:permission:delete"))])
def delete_permission(permission_id: int, db: Session = Depends(get_db)) -> dict:
    permission = _get_permission(db, permission_id)
    db.query(RolePermission).filter(RolePermission.permission_id == permission_id).delete(
        synchronize_session=False
    )
    permission.deleted = 1
    db.commit()
    invalidate_all_authz()
    return {"id": permission_id, "deleted": True}


# ------------------------------------------------------------------ 用户授权
@router.get("/users", dependencies=[Depends(require_permission("rbac:user:list"))])
def list_users(
    keyword: str | None = Query(None, max_length=64),
    role_code: str | None = Query(None, max_length=32),
    status: int | None = Query(None, ge=0, le=1),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(User).where(User.deleted == 0)
    if keyword:
        stmt = stmt.where(or_(
            User.username.contains(keyword),
            User.nickname.contains(keyword),
            User.email.contains(keyword),
            User.open_id.contains(keyword),
        ))
    if role_code:
        stmt = stmt.where(
            User.id.in_(
                select(UserRole.user_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.role_code == role_code, Role.deleted == 0)
            )
        )
    if status is not None:
        stmt = stmt.where(User.status == status)
    page = paginate(
        db, stmt, page_params,
        allowed_sort={"id": User.id, "username": User.username,
                      "created_at": User.created_at, "last_login_at": User.last_login_at},
        default_sort="id:desc",
    )
    page["items"] = [_user_dict(db, u) for u in page["items"]]
    return page


@router.put("/users/{user_id}/roles",
            dependencies=[Depends(require_permission("rbac:user:grant"))])
def grant_user_roles(
    user_id: int,
    payload: RoleIdsIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    user = db.scalar(select(User).where(User.id == user_id, User.deleted == 0))
    if not user:
        raise NotFoundError("用户不存在")
    roles = list(
        db.scalars(
            select(Role).where(Role.id.in_(payload.role_ids), Role.deleted == 0, Role.status == 1)
        )
    ) if payload.role_ids else []
    if payload.role_ids and len(roles) != len(set(payload.role_ids)):
        raise ValidationError("存在无效或已禁用的角色")

    role_codes = [r.role_code for r in roles]
    if user.id == current.id and "ADMIN" not in role_codes:
        raise ValidationError("不能移除当前登录管理员自己的 ADMIN 角色")

    db.query(UserRole).filter(UserRole.user_id == user_id).delete(synchronize_session=False)
    for role in roles:
        db.add(UserRole(user_id=user_id, role_id=role.id))

    if "ADMIN" in role_codes:
        user.role = "ADMIN"
    elif role_codes:
        user.role = role_codes[0]
    else:
        user.role = "USER"

    db.commit()
    invalidate_user_authz(user.id)
    revoke_user_sessions(user.id)
    return _user_dict(db, user)


@router.get("/users/{user_id}/authz",
            dependencies=[Depends(require_permission("rbac:user:list"))])
def user_authz(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.id == user_id, User.deleted == 0))
    if not user:
        raise NotFoundError("用户不存在")
    authz = load_user_authz(db, user)
    return {
        "user_id": user.id,
        "username": user.username,
        "roles": authz.get("roles", []),
        "permissions": authz.get("permissions", []),
        "menus": authz.get("menus", []),
        "is_admin": authz.get("is_admin", False),
    }
