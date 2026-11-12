"""Redis 会话存储：令牌、用户身份与角色权限快照。"""
import json
import time

from app.common.config import settings
from app.common.redis_client import get_redis
from app.common.security import token_digest

SESSION_PREFIX = "auth:session:"
USER_SESSIONS_PREFIX = "auth:user_sessions:"


def _session_key(token: str) -> str:
    return f"{SESSION_PREFIX}{token_digest(token)}"


def create_session(
    token: str,
    user_id: int,
    role: str,
    *,
    username: str | None = None,
    nickname: str | None = None,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    ip: str | None = None,
    ttl_s: int | None = None,
) -> None:
    ttl = ttl_s or settings.auth_token_ttl_s
    payload = {
        "user_id": user_id,
        "role": role,
        "username": username,
        "nickname": nickname,
        "roles": roles or [role],
        "permissions": permissions or [],
        "login_ip": ip,
        "login_at": int(time.time()),
    }
    client = get_redis()
    client.set(_session_key(token), json.dumps(payload, ensure_ascii=False), ex=ttl)
    client.sadd(f"{USER_SESSIONS_PREFIX}{user_id}", token_digest(token))
    client.expire(f"{USER_SESSIONS_PREFIX}{user_id}", ttl)


def get_session(token: str) -> dict | None:
    raw = get_redis().get(_session_key(token))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def touch_session(token: str, ttl_s: int | None = None) -> None:
    get_redis().expire(_session_key(token), ttl_s or settings.auth_token_ttl_s)


def revoke_session(token: str, user_id: int | None = None) -> None:
    client = get_redis()
    digest = token_digest(token)
    client.delete(_session_key(token))
    if user_id:
        client.srem(f"{USER_SESSIONS_PREFIX}{user_id}", digest)


def revoke_user_sessions(user_id: int) -> int:
    client = get_redis()
    digests = client.smembers(f"{USER_SESSIONS_PREFIX}{user_id}")
    count = 0
    for digest in digests:
        count += client.delete(f"{SESSION_PREFIX}{digest}")
    client.delete(f"{USER_SESSIONS_PREFIX}{user_id}")
    return count


def session_count(user_id: int) -> int:
    return len(get_redis().smembers(f"{USER_SESSIONS_PREFIX}{user_id}"))
