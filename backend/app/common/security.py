import base64
import hashlib
import hmac
import json
import secrets
import time

from app.common.config import settings
from app.common.errors import UnauthorizedError

PASSWORD_PREFIX = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = settings.password_iterations
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), iterations)
    return f"{PASSWORD_PREFIX}${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        prefix, iterations, salt, expected = stored.split("$", 3)
        if prefix != PASSWORD_PREFIX:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(body: str) -> str:
    digest = hmac.new(settings.auth_secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256)
    return _b64encode(digest.digest())


def issue_token(user_id: int, role: str, ttl_s: int | None = None) -> tuple[str, int]:
    """签发无状态访问令牌，返回 (token, expires_in)。"""
    ttl = ttl_s or settings.auth_token_ttl_s
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}", ttl


def decode_token(token: str) -> dict:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise UnauthorizedError("令牌格式非法") from exc
    if not hmac.compare_digest(signature, _sign(body)):
        raise UnauthorizedError("令牌签名校验失败")
    try:
        payload = json.loads(_b64decode(body))
    except Exception as exc:
        raise UnauthorizedError("令牌内容非法") from exc
    if int(payload.get("exp", 0)) <= int(time.time()):
        raise UnauthorizedError("令牌已过期，请重新登录")
    return payload
