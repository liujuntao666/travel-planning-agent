from datetime import datetime
from typing import Callable

from fastapi import Depends, Request
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.common.db import get_db
from app.common.errors import AppError, ForbiddenError, LockedError, UnauthorizedError
from app.models import AuthToken, GroupMember, GroupPriv, User


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    token = request.headers.get("X-Auth-Token")
    if not token:
        raise UnauthorizedError()

    record = db.scalar(select(AuthToken).where(AuthToken.token == token))
    now = datetime.now()
    if record is None or record.revoked or record.expires_at <= now:
        raise UnauthorizedError()

    user = db.scalar(select(User).where(User.account == record.account))
    if user is None or user.status == "deleted":
        raise UnauthorizedError()

    if user.status == "locked":
        if user.locked_until and user.locked_until > now:
            raise LockedError(
                f"账号已锁定，请于 {user.locked_until.strftime('%Y-%m-%d %H:%M:%S')} 后重试"
            )
        user.status = "active"
        user.login_fails = 0
        user.locked_until = None
        db.commit()

    return user


def permission_source(db: Session, user: User, module: str, method: str) -> str:
    """返回权限判定来源：ADMIN / GROUP / NONE。"""
    if user.admin == "yes":
        return "ADMIN"
    found = db.scalar(
        select(GroupPriv.id)
        .join(
            GroupMember,
            and_(
                GroupMember.group_id == GroupPriv.group_id,
                GroupMember.account == user.account,
            ),
        )
        .where(GroupPriv.module == module, GroupPriv.method == method)
        .limit(1)
    )
    return "GROUP" if found is not None else "NONE"


def require_perm(module: str, method: str) -> Callable[..., User]:
    def dependency(
        user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        if permission_source(db, user, module, method) == "NONE":
            raise ForbiddenError(f"无权限：{module}-{method}")
        return user

    return dependency


def ensure_admin(user: User) -> None:
    if user.admin != "yes":
        raise AppError("FORBIDDEN", "仅超级管理员可执行该操作", 403)
