"""Redis 客户端：会话、验证码、限流、权限与字典缓存共用。

默认优先连接 Redis；不可用时退化为进程内存储，保证本地无 Redis 也能启动，
但生产与验收环境必须配置 REDIS_URL（docker compose 已内置 redis 服务）。
"""
import fnmatch
import json
import threading
import time
from typing import Set

from app.common.config import settings
from app.common.logging import get_logger

log = get_logger(__name__)
_lock = threading.Lock()
_client = None
_backend = "uninitialized"


class MemoryRedis:
    """最小可用的 Redis 替代实现，仅覆盖本项目使用到的命令。"""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._expires: dict[str, float] = {}
        self._sets: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def _expired(self, key: str) -> bool:
        deadline = self._expires.get(key)
        if deadline is not None and deadline <= time.time():
            self._data.pop(key, None)
            self._expires.pop(key, None)
            self._sets.pop(key, None)
            return True
        return False

    def get(self, key: str) -> str | None:
        with self._lock:
            if self._expired(key):
                return None
            return self._data.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        with self._lock:
            self._data[key] = value
            if ex:
                self._expires[key] = time.time() + ex
            else:
                self._expires.pop(key, None)
            return True

    def delete(self, *keys: str) -> int:
        removed = 0
        with self._lock:
            for key in keys:
                removed += 1 if self._data.pop(key, None) is not None else 0
                self._expires.pop(key, None)
                self._sets.pop(key, None)
        return removed

    def exists(self, key: str) -> int:
        with self._lock:
            return 0 if self._expired(key) else int(key in self._data or key in self._sets)

    def incr(self, key: str, amount: int = 1) -> int:
        with self._lock:
            if self._expired(key):
                current = 0
            else:
                current = int(self._data.get(key, "0"))
            current += amount
            self._data[key] = str(current)
            return current

    def expire(self, key: str, seconds: int) -> bool:
        with self._lock:
            if key in self._data or key in self._sets:
                self._expires[key] = time.time() + seconds
                return True
            return False

    def ttl(self, key: str) -> int:
        with self._lock:
            if self._expired(key):
                return -2
            deadline = self._expires.get(key)
            return int(deadline - time.time()) if deadline else -1

    def keys(self, pattern: str = "*") -> list[str]:
        with self._lock:
            for key in list(self._data):
                self._expired(key)
            return [key for key in self._data if fnmatch.fnmatch(key, pattern)]

    def sadd(self, key: str, *values: str) -> int:
        with self._lock:
            bucket = self._sets.setdefault(key, set())
            before = len(bucket)
            bucket.update(values)
            return len(bucket) - before

    def srem(self, key: str, *values: str) -> int:
        with self._lock:
            bucket = self._sets.get(key)
            if not bucket:
                return 0
            before = len(bucket)
            bucket.difference_update(values)
            return before - len(bucket)

    def smembers(self, key: str) -> Set[str]:
        with self._lock:
            return set(self._sets.get(key, set()))

    def ping(self) -> bool:
        return True


def get_redis():
    """返回 Redis 客户端；首次调用时探测连接，失败则降级为内存实现。"""
    global _client, _backend
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        try:
            import redis

            client = redis.Redis.from_url(
                settings.redis_url, decode_responses=True, socket_connect_timeout=2
            )
            client.ping()
            _client = client
            _backend = "redis"
            log.info("redis_connected: %s", settings.redis_url)
        except Exception as exc:  # noqa: BLE001
            if settings.redis_required:
                raise RuntimeError(f"Redis 不可用：{exc}") from exc
            _client = MemoryRedis()
            _backend = "memory"
            log.warning("redis_unavailable_fallback_memory: %s", exc)
        return _client


def redis_backend() -> str:
    get_redis()
    return _backend


def cache_get(key: str) -> str | None:
    return get_redis().get(key)


def cache_set(key: str, value: str, ttl_s: int | None = None) -> None:
    get_redis().set(key, value, ex=ttl_s)


def cache_delete(*keys: str) -> None:
    if keys:
        get_redis().delete(*keys)


def cache_delete_pattern(pattern: str) -> None:
    client = get_redis()
    for key in client.keys(pattern):
        client.delete(key)


def cache_get_json(key: str) -> dict | list | None:
    raw = cache_get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def cache_set_json(key: str, value: dict | list, ttl_s: int) -> None:
    cache_set(key, json.dumps(value, ensure_ascii=False), ttl_s)
