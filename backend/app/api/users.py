from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_core.dialog import get_or_create_user
from app.common.auth import ensure_owner, get_current_user
from app.common.auth_session import create_session
from app.common.config import settings
from app.common.db import get_db
from app.common.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.common.ratelimit import enforce
from app.common.rbac import load_user_authz
from app.common.security import issue_token
from app.models import Conversation, User
from app.schemas.requests import ConversationIn, LoginIn

router = APIRouter(tags=["users"])


@router.post("/users/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """演示用 OpenID 免密登录：保留多登录方式，同时接入 Redis 会话与限流。"""
    ip = request.client.host if request.client else "unknown"
    enforce(
        f"login:ip:{ip}",
        settings.login_rate_limit,
        settings.login_rate_window_s,
        "登录请求过于频繁，请稍后再试",
    )
    user = get_or_create_user(db, payload.open_id, payload.nickname, payload.source)
    db.commit()
    if (user.status or 1) != 1:
        raise UnauthorizedError("账号已被禁用")
    authz = load_user_authz(db, user)
    token, expires_in = issue_token(user.id, user.role)
    create_session(
        token,
        user.id,
        user.role,
        username=user.username,
        nickname=user.nickname,
        roles=authz.get("roles", []),
        permissions=authz.get("permissions", []),
        ip=ip,
    )
    return {
        "id": user.id,
        "open_id": user.open_id,
        "username": user.username,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "source": user.source,
        "role": user.role,
        "status": user.status,
        "roles": authz.get("roles", []),
        "permissions": authz.get("permissions", []),
        "menus": authz.get("menus", []),
        "is_admin": authz.get("is_admin", False),
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }


@router.get("/users/{user_id}")
def user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    ensure_owner(current, user_id)
    user = db.scalar(select(User).where(User.id == user_id, User.deleted == 0))
    if not user:
        raise NotFoundError("用户不存在")
    conversations = db.scalars(
        select(Conversation).where(Conversation.user_id == user.id, Conversation.deleted == 0)
        .order_by(Conversation.id.desc()).limit(20)
    ).all()
    return {
        "id": user.id,
        "open_id": user.open_id,
        "nickname": user.nickname,
        "role": user.role,
        "conversations": [
            {"id": c.id, "title": c.title, "last_intent": c.last_intent,
             "current_trip_id": c.current_trip_id, "last_message_at": c.last_message_at}
            for c in conversations
        ],
    }


@router.post("/conversations")
def create_conversation(
    payload: ConversationIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    from app.agent_core.dialog import create_conversation as _create

    if current.role != "ADMIN" and payload.user_id != current.id:
        raise ForbiddenError("只能为本人创建会话")
    user = db.scalar(select(User).where(User.id == payload.user_id, User.deleted == 0))
    if not user:
        raise NotFoundError("用户不存在")
    conversation = _create(db, user, payload.title)
    db.commit()
    return {"id": conversation.id, "user_id": conversation.user_id, "title": conversation.title}
