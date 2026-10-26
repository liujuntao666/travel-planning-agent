from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.common.db import get_db
from app.common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.common.helpers import (
    dept_name,
    effective_privileges,
    fmt_user_row,
    group_briefs,
    log_action,
    paginate,
    user_payload,
)
from app.deps import get_current_user, permission_source, require_perm
from app.models import AuthToken, Dept, Group, GroupMember, User
from app.schemas import GroupIdsRequest, ResetPasswordRequest, UserCreateRequest, UserPatchRequest

router = APIRouter(tags=["users"])


def _get_user(db: Session, account: str) -> User:
    user = db.scalar(select(User).where(User.account == account))
    if user is None or user.status == "deleted":
        raise NotFoundError("用户不存在")
    return user


def _get_groups_or_422(db: Session, group_ids: list[int]) -> list[Group]:
    ids = sorted(set(group_ids))
    if not ids:
        return []
    groups = db.scalars(select(Group).where(Group.id.in_(ids))).all()
    if len(groups) != len(ids):
        raise ValidationError("存在无效的用户组 ID")
    return groups


def _admin_count(db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.admin == "yes", User.status != "deleted")
        )
        or 0
    )


@router.get("/users")
def list_users(
    keyword: str | None = None,
    dept_id: int | None = None,
    group_id: int | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(require_perm("user", "browse")),
    db: Session = Depends(get_db),
) -> dict:
    conditions = []
    if status:
        conditions.append(User.status == status)
    else:
        conditions.append(User.status != "deleted")
    if keyword:
        like = f"%{keyword}%"
        conditions.append(or_(User.account.like(like), User.realname.like(like)))
    if dept_id is not None:
        dept = db.get(Dept, dept_id)
        if dept is None:
            raise NotFoundError("部门不存在")
        conditions.append(
            User.dept_id.in_(
                select(Dept.id).where(Dept.path.like(f"{dept.path}%"))
            )
        )
    if group_id is not None:
        conditions.append(
            User.account.in_(
                select(GroupMember.account).where(GroupMember.group_id == group_id)
            )
        )

    page, page_size, offset = paginate(page, page_size)
    total = (
        db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0
    )
    rows = db.execute(
        select(User, Dept.name)
        .outerjoin(Dept, Dept.id == User.dept_id)
        .where(*conditions)
        .order_by(Dept.path.asc(), User.account.asc())
        .offset(offset)
        .limit(page_size)
    ).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [fmt_user_row(row[0], row[1]) for row in rows],
    }


@router.post("/users")
def create_user(
    payload: UserCreateRequest,
    request: Request,
    user: User = Depends(require_perm("user", "create")),
    db: Session = Depends(get_db),
) -> dict:
    if db.scalar(select(User.id).where(User.account == payload.account)) is not None:
        raise ConflictError("账号已存在")
    dept = db.get(Dept, payload.dept_id)
    if dept is None:
        raise ValidationError("部门不存在")
    groups = _get_groups_or_422(db, payload.group_ids)

    target = User(
        account=payload.account,
        realname=payload.realname,
        password=payload.password,
        dept_id=payload.dept_id,
        role=payload.role,
        admin="no",
        status="active",
        email=payload.email,
        phone=payload.phone,
    )
    db.add(target)
    db.flush()
    for group in groups:
        db.add(GroupMember(account=target.account, group_id=group.id))
    log_action(
        db, request=request, user=user, module="user", method="create",
        message=f"创建用户 {target.account}", params=payload,
    )
    db.commit()
    return {"id": target.id, "account": target.account}


@router.get("/users/{account}")
def get_user(
    account: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    target = _get_user(db, account)
    if (
        target.account != user.account
        and user.admin != "yes"
        and permission_source(db, user, "user", "view") == "NONE"
    ):
        raise ForbiddenError("无权限查看该用户")
    payload = user_payload(db, target, with_groups=False)
    payload["email"] = target.email
    payload["phone"] = target.phone
    payload["groups"] = group_briefs(db, target.account)
    payload["privileges"] = effective_privileges(db, target)
    return payload


@router.patch("/users/{account}")
def update_user(
    account: str,
    payload: UserPatchRequest,
    request: Request,
    user: User = Depends(require_perm("user", "edit")),
    db: Session = Depends(get_db),
) -> dict:
    target = _get_user(db, account)

    if payload.admin is not None:
        if user.admin != "yes":
            raise ForbiddenError("仅超级管理员可设置 admin 字段")
        if payload.admin == "no" and target.admin == "yes" and _admin_count(db) <= 1:
            raise ConflictError("不允许降级最后一个超级管理员")
        target.admin = payload.admin

    if payload.dept_id is not None:
        if db.get(Dept, payload.dept_id) is None:
            raise ValidationError("部门不存在")
        target.dept_id = payload.dept_id
    if payload.realname is not None:
        target.realname = payload.realname
    if payload.role is not None:
        target.role = payload.role
    if payload.email is not None:
        target.email = payload.email
    if payload.phone is not None:
        target.phone = payload.phone
    if payload.status is not None:
        target.status = payload.status
        if payload.status == "active":
            target.login_fails = 0
            target.locked_until = None

    log_action(
        db, request=request, user=user, module="user", method="edit",
        message=f"修改用户 {target.account}", params=payload,
    )
    db.commit()
    return {"success": True}


@router.delete("/users/{account}")
def delete_user(
    account: str,
    request: Request,
    user: User = Depends(require_perm("user", "delete")),
    db: Session = Depends(get_db),
) -> dict:
    target = _get_user(db, account)
    if target.account == user.account:
        raise ConflictError("不能删除当前登录账号")
    if target.admin == "yes" and _admin_count(db) <= 1:
        raise ConflictError("不能删除最后一个超级管理员")

    target.status = "deleted"
    db.execute(
        update(AuthToken).where(AuthToken.account == target.account).values(revoked=True)
    )
    log_action(
        db, request=request, user=user, module="user", method="delete",
        message=f"删除用户 {target.account}",
    )
    db.commit()
    return {"success": True}


@router.post("/users/{account}/unlock")
def unlock_user(
    account: str,
    request: Request,
    user: User = Depends(require_perm("user", "unlock")),
    db: Session = Depends(get_db),
) -> dict:
    target = _get_user(db, account)
    target.status = "active"
    target.login_fails = 0
    target.locked_until = None
    log_action(
        db, request=request, user=user, module="user", method="unlock",
        message=f"解锁账号 {target.account}",
    )
    db.commit()
    return {"success": True}


@router.post("/users/{account}/reset-password")
def reset_password(
    account: str,
    payload: ResetPasswordRequest,
    request: Request,
    user: User = Depends(require_perm("user", "resetpwd")),
    db: Session = Depends(get_db),
) -> dict:
    target = _get_user(db, account)
    target.password = payload.new_password
    db.execute(
        update(AuthToken).where(AuthToken.account == target.account).values(revoked=True)
    )
    log_action(
        db, request=request, user=user, module="user", method="resetpwd",
        message=f"重置密码 {target.account}", params=payload,
    )
    db.commit()
    return {"success": True}


@router.put("/users/{account}/groups")
def set_user_groups(
    account: str,
    payload: GroupIdsRequest,
    request: Request,
    user: User = Depends(require_perm("user", "assigngroup")),
    db: Session = Depends(get_db),
) -> dict:
    target = _get_user(db, account)
    groups = _get_groups_or_422(db, payload.group_ids)

    db.execute(delete(GroupMember).where(GroupMember.account == target.account))
    for group in groups:
        db.add(GroupMember(account=target.account, group_id=group.id))
    log_action(
        db, request=request, user=user, module="user", method="assigngroup",
        message=f"设置用户组 {target.account}", params=payload,
    )
    db.commit()
    return {
        "success": True,
        "groups": [{"id": g.id, "name": g.name, "role": g.role} for g in groups],
    }
