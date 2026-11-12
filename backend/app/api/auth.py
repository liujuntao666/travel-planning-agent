"""认证接口：验证码、注册、登录、登出、当前用户权限、忘记密码重置。"""
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.common.auth import get_current_user, bearer_scheme
from app.common.auth_session import (
    create_session,
    revoke_session,
    revoke_user_sessions,
    session_count,
)
from app.common.captcha import generate_captcha, verify_captcha
from app.common.config import settings
from app.common.db import get_db
from app.common.errors import ConflictError, UnauthorizedError, ValidationError
from app.common.ratelimit import (
    clear_login_failures,
    enforce,
    login_locked,
    record_login_failure,
)
from app.common.rbac import invalidate_user_authz, load_user_authz
from app.common.redis_client import (
    cache_delete,
    cache_get,
    cache_set,
    redis_backend,
)
from app.common.security import hash_password, issue_token, token_digest, verify_password
from app.models import Role, User, UserRole
from app.schemas.auth import (
    ForgotPasswordIn,
    PasswordLoginIn,
    RegisterIn,
    ResetPasswordIn,
)

router = APIRouter(prefix="/auth", tags=["auth"])

RESET_PREFIX = "pwd:reset:"


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "open_id": user.open_id,
        "nickname": user.nickname,
        "email": user.email,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "status": user.status,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def _primary_role(authz: dict, user: User) -> str:
    if authz.get("is_admin"):
        return "ADMIN"
    roles = authz.get("roles") or []
    return roles[0] if roles else user.role


def _login_payload(db: Session, user: User, token: str, expires_in: int, authz: dict) -> dict:
    return {
        "user": _user_dict(user),
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "roles": authz.get("roles", []),
        "permissions": authz.get("permissions", []),
        "menus": authz.get("menus", []),
        "is_admin": authz.get("is_admin", False),
    }


def _issue_login(db: Session, user: User, ip: str) -> dict:
    authz = load_user_authz(db, user)
    token, expires_in = issue_token(user.id, _primary_role(authz, user))
    create_session(
        token,
        user.id,
        _primary_role(authz, user),
        username=user.username,
        nickname=user.nickname,
        roles=authz.get("roles", []),
        permissions=authz.get("permissions", []),
        ip=ip,
    )
    return _login_payload(db, user, token, expires_in, authz)


@router.get("/captcha")
def captcha() -> dict:
    return generate_captcha()


@router.post("/register")
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = client_ip(request)
    enforce(
        f"register:ip:{ip}",
        settings.register_rate_limit,
        settings.register_rate_window_s,
        "注册请求过于频繁，请稍后再试",
    )
    if not verify_captcha(payload.captcha_id, payload.captcha_code):
        raise ValidationError("验证码错误或已失效")

    exists = db.scalar(
        select(User).where(
            or_(User.username == payload.username, User.open_id == f"acct:{payload.username}")
        )
    )
    if exists:
        raise ConflictError("用户名已被占用")

    user = User(
        open_id=f"acct:{payload.username}",
        username=payload.username,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname or payload.username,
        email=payload.email,
        phone=payload.phone,
        source="WEB",
        role="USER",
        status=1,
    )
    db.add(user)
    db.flush()
    role = db.scalar(select(Role).where(Role.role_code == "USER", Role.deleted == 0))
    if role:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    return _issue_login(db, user, ip)


@router.post("/login")
def login(payload: PasswordLoginIn, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = client_ip(request)
    enforce(
        f"login:ip:{ip}",
        settings.login_rate_limit,
        settings.login_rate_window_s,
        "登录请求过于频繁，请稍后再试",
    )
    if login_locked(payload.username, ip):
        raise UnauthorizedError("登录失败次数过多，账号已临时锁定，请稍后再试")
    if not verify_captcha(payload.captcha_id, payload.captcha_code):
        raise ValidationError("验证码错误或已失效")

    user = db.scalar(
        select(User).where(User.username == payload.username, User.deleted == 0)
    )
    if not user or not verify_password(payload.password, user.password_hash):
        record_login_failure(payload.username, ip)
        raise UnauthorizedError("账号或密码错误")
    if (user.status or 1) != 1:
        raise UnauthorizedError("账号已被禁用，请联系管理员")

    clear_login_failures(payload.username, ip)
    user.last_login_at = datetime.now()
    db.commit()
    return _issue_login(db, user, ip)


@router.post("/logout")
def logout(
    current: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials:
        revoke_session(credentials.credentials, current.id)
    return {"message": "已安全退出登录"}


@router.get("/me")
def me(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    authz = load_user_authz(db, current)
    return {
        "user": _user_dict(current),
        "roles": authz.get("roles", []),
        "permissions": authz.get("permissions", []),
        "menus": authz.get("menus", []),
        "is_admin": authz.get("is_admin", False),
        "session": {
            "count": session_count(current.id),
            "backend": redis_backend(),
        },
    }


@router.post("/password/forgot")
def forgot_password(
    payload: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)
) -> dict:
    ip = client_ip(request)
    enforce(f"forgot:ip:{ip}", 5, 300, "找回密码请求过于频繁，请稍后再试")
    if not verify_captcha(payload.captcha_id, payload.captcha_code):
        raise ValidationError("验证码错误或已失效")

    user = db.scalar(
        select(User).where(
            User.deleted == 0,
            or_(User.username == payload.account, User.email == payload.account),
        )
    )
    response = {
        "message": "如果账号存在，重置凭证已生成，请在有效期内完成重置",
        "expires_in": settings.password_reset_ttl_s,
    }
    if not user:
        response["reset_token"] = None
        return response

    token = secrets.token_urlsafe(32)
    cache_delete(f"{RESET_PREFIX}{token_digest(token)}")
    from app.common.redis_client import cache_set

    cache_set(
        f"{RESET_PREFIX}{token_digest(token)}",
        str(user.id),
        settings.password_reset_ttl_s,
    )
    response["reset_token"] = token
    return response


@router.post("/password/reset")
def reset_password(
    payload: ResetPasswordIn, request: Request, db: Session = Depends(get_db)
) -> dict:
    ip = client_ip(request)
    enforce(f"reset:ip:{ip}", 10, 300, "重置请求过于频繁，请稍后再试")

    key = f"{RESET_PREFIX}{token_digest(payload.reset_token)}"
    raw = cache_get(key)
    if not raw:
        raise ValidationError("重置凭证无效或已过期")
    user = db.scalar(select(User).where(User.id == int(raw), User.deleted == 0))
    if not user:
        raise ValidationError("账号不存在或已被删除")

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    cache_delete(key)
    revoke_user_sessions(user.id)
    invalidate_user_authz(user.id)
    clear_login_failures(user.username or "", ip)
    return {"message": "密码已重置，请使用新密码登录"}
