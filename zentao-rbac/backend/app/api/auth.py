from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.common.config import settings
from app.common.db import get_db
from app.common.errors import LockedError, NotFoundError, UnauthorizedError
from app.common.helpers import (
    data_scope_ids,
    effective_privileges,
    group_briefs,
    log_action,
    user_payload,
)
from app.common.security import new_token
from app.deps import get_current_user
from app.models import AuthToken, User
from app.schemas import ChangePasswordRequest, LoginRequest

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
def login(
    payload: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    now = datetime.now()
    user = db.scalar(select(User).where(User.account == payload.account))

    if user is None or user.status == "deleted":
        log_action(
            db, request=request, account=payload.account, module="auth", method="login",
            result="FAIL", message="账号或密码错误", params=payload,
        )
        db.commit()
        raise UnauthorizedError("账号或密码错误")

    if user.status == "locked":
        if user.locked_until is None or user.locked_until > now:
            until = user.locked_until.strftime("%Y-%m-%d %H:%M:%S") if user.locked_until else "10 分钟"
            log_action(
                db, request=request, user=user, module="auth", method="login",
                result="FAIL", message="账号已锁定", params=payload,
            )
            db.commit()
            raise LockedError(f"账号已锁定，请于 {until} 后重试")
        user.status = "active"
        user.login_fails = 0
        user.locked_until = None

    if payload.password != user.password:
        user.login_fails += 1
        if user.login_fails >= settings.login_max_fails:
            user.status = "locked"
            user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
        log_action(
            db, request=request, user=user, module="auth", method="login",
            result="FAIL", message="账号或密码错误", params=payload,
        )
        db.commit()
        raise UnauthorizedError("账号或密码错误")

    user.login_fails = 0
    user.locked_until = None
    user.status = "active"
    user.last_login = now

    ttl = settings.remember_ttl_seconds if payload.remember else settings.token_ttl_seconds
    token = new_token()
    db.add(
        AuthToken(
            token=token,
            account=user.account,
            expires_at=now + timedelta(seconds=ttl),
        )
    )
    log_action(
        db, request=request, user=user, module="auth", method="login",
        result="SUCCESS", message="登录成功", params=payload,
    )
    db.commit()

    return {
        "token": token,
        "expires_in": ttl,
        "user": user_payload(db, user),
    }


@router.post("/auth/logout")
def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    token = request.headers.get("X-Auth-Token")
    if token:
        db.execute(
            update(AuthToken)
            .where(AuthToken.token == token)
            .values(revoked=True)
        )
    log_action(db, request=request, user=user, module="auth", method="logout")
    db.commit()
    return {"success": True}


@router.get("/auth/me")
def me(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    payload = user_payload(db, user, with_groups=False)
    payload["groups"] = group_briefs(db, user.account)
    payload["privileges"] = effective_privileges(db, user)
    payload["data_scope"] = data_scope_ids(db, user)
    return payload


@router.patch("/auth/me/password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if payload.old_password != user.password:
        raise UnauthorizedError("原密码不正确")

    user.password = payload.new_password
    token = request.headers.get("X-Auth-Token")
    db.execute(
        update(AuthToken)
        .where(AuthToken.account == user.account, AuthToken.token != token)
        .values(revoked=True)
    )
    log_action(
        db, request=request, user=user, module="auth", method="password",
        message="修改本人密码", params=payload,
    )
    db.commit()
    return {"success": True}
