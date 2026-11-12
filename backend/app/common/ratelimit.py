"""基于 Redis 的请求限流与登录失败锁定。"""
from app.common.config import settings
from app.common.errors import TooManyRequestsError
from app.common.redis_client import get_redis

RATE_PREFIX = "rate:"
LOGIN_FAIL_PREFIX = "login:fail:"


def hit(key: str, limit: int, window_s: int) -> bool:
    """计数并返回是否仍在阈值内。首次计数时设置窗口过期时间。"""
    client = get_redis()
    full_key = f"{RATE_PREFIX}{key}"
    count = client.incr(full_key)
    if count == 1:
        client.expire(full_key, window_s)
    return count <= limit


def enforce(key: str, limit: int, window_s: int, message: str) -> None:
    if not hit(key, limit, window_s):
        raise TooManyRequestsError(message)


def record_login_failure(account: str, ip: str) -> tuple[int, int]:
    client = get_redis()
    account_key = f"{LOGIN_FAIL_PREFIX}account:{account.lower()}"
    ip_key = f"{LOGIN_FAIL_PREFIX}ip:{ip}"
    account_count = client.incr(account_key)
    if account_count == 1:
        client.expire(account_key, settings.login_lock_s)
    ip_count = client.incr(ip_key)
    if ip_count == 1:
        client.expire(ip_key, settings.login_lock_s)
    return account_count, ip_count


def login_locked(account: str, ip: str) -> bool:
    client = get_redis()
    account_count = int(client.get(f"{LOGIN_FAIL_PREFIX}account:{account.lower()}") or 0)
    ip_count = int(client.get(f"{LOGIN_FAIL_PREFIX}ip:{ip}") or 0)
    return (
        account_count >= settings.login_max_failures or ip_count >= settings.login_max_failures
    )


def clear_login_failures(account: str, ip: str) -> None:
    get_redis().delete(
        f"{LOGIN_FAIL_PREFIX}account:{account.lower()}",
        f"{LOGIN_FAIL_PREFIX}ip:{ip}",
    )
