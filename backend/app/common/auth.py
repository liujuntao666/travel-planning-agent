from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth_session import get_session, touch_session
from app.common.db import get_db
from app.common.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.common.security import decode_token
from app.models import Conversation, Trip, User

bearer_scheme = HTTPBearer(auto_error=False, description="登录接口返回的 Bearer 令牌")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise UnauthorizedError()
    token = credentials.credentials
    payload = decode_token(token)
    session = get_session(token)
    if not session or int(session.get("user_id", 0)) != int(payload.get("sub", 0)):
        raise UnauthorizedError("登录会话已失效，请重新登录")
    touch_session(token)
    user = db.scalar(select(User).where(User.id == int(payload.get("sub", 0)), User.deleted == 0))
    if not user:
        raise UnauthorizedError("用户不存在")
    if (user.status or 1) != 1:
        raise UnauthorizedError("账号已被禁用")
    return user


def require_roles(*roles: str):
    """RBAC：限定角色集合，ADMIN 默认拥有全部权限。"""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles and user.role != "ADMIN":
            raise ForbiddenError("当前角色无权访问该资源")
        return user

    return dependency


def ensure_owner(user: User, owner_id: int) -> None:
    if user.role == "ADMIN":
        return
    if owner_id != user.id:
        raise ForbiddenError("无权访问他人的资源")


def get_owned_conversation(db: Session, conversation_id: int, user: User) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.deleted == 0)
    )
    if not conversation:
        raise NotFoundError("会话不存在")
    ensure_owner(user, conversation.user_id)
    return conversation


def get_owned_trip(db: Session, trip_id: int, user: User) -> Trip:
    trip = db.scalar(select(Trip).where(Trip.id == trip_id, Trip.deleted == 0))
    if not trip:
        raise NotFoundError("行程不存在")
    ensure_owner(user, trip.user_id)
    return trip
