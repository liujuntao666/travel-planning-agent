import hashlib
import json
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from app.common.config import settings
from app.common.db import SessionLocal
from app.common.security import decode_token
from app.models import IdempotencyRecord

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# 认证类接口（验证码/密码登录、注册、找回）天然可重试，不要求请求标识
EXEMPT_PATHS = {
    f"{settings.api_prefix}/auth/login",
    f"{settings.api_prefix}/auth/register",
    f"{settings.api_prefix}/auth/logout",
    f"{settings.api_prefix}/auth/password/forgot",
    f"{settings.api_prefix}/auth/password/reset",
}


def _json_response(status: int, payload: dict, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=payload, headers=headers or {})


async def _read_body(receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        chunks.append(message.get("body", b""))
        if not message.get("more_body"):
            break
    return b"".join(chunks)


def _replay_receive(body: bytes):
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


def _caller_id(headers: Headers) -> int | None:
    authorization = headers.get("authorization") or ""
    if not authorization.startswith("Bearer "):
        return None
    try:
        return int(decode_token(authorization[7:].strip()).get("sub"))
    except Exception:
        return None


def _finish(key: str, status: int, body: bytes, content_type: str) -> None:
    if not (200 <= status < 300) or "application/json" not in content_type:
        _drop(key)
        return
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        _drop(key)
        return
    with SessionLocal() as db:
        record = db.get(IdempotencyRecord, key)
        if not record:
            return
        record.state = "DONE"
        record.status_code = status
        record.response_body = text
        db.commit()


def _drop(key: str) -> None:
    with SessionLocal() as db:
        record = db.get(IdempotencyRecord, key)
        if record:
            db.delete(record)
            db.commit()


class IdempotencyMiddleware:
    """唯一请求标识方案：写操作按 Idempotency-Key 去重，成功响应可回放。"""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        if (
            method not in MUTATING_METHODS
            or not path.startswith(settings.api_prefix)
            or path.endswith("/messages/stream")
            or path in EXEMPT_PATHS
        ):
            return await self.app(scope, receive, send)

        headers = Headers(scope=scope)
        key = (headers.get("idempotency-key") or headers.get("x-request-id") or "").strip()
        if not key:
            response = _json_response(
                422,
                {"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "写操作必须携带 Idempotency-Key 请求头"},
            )
            return await response(scope, receive, send)
        if len(key) > 64:
            response = _json_response(
                422,
                {"code": "IDEMPOTENCY_KEY_INVALID", "message": "Idempotency-Key 长度不得超过 64"},
            )
            return await response(scope, receive, send)

        body = await _read_body(receive)
        replay_receive = _replay_receive(body)
        digest = hashlib.sha256(body).hexdigest()
        user_id = _caller_id(headers)

        with SessionLocal() as db:
            record = db.get(IdempotencyRecord, key)
            if record and record.expires_at and record.expires_at < datetime.now():
                db.delete(record)
                db.commit()
                record = None
            if record:
                if (
                    record.method != method
                    or record.path != path
                    or record.request_hash != digest
                ):
                    response = _json_response(
                        422,
                        {
                            "code": "IDEMPOTENCY_KEY_REUSED",
                            "message": "该请求标识已用于不同的请求内容",
                        },
                    )
                    return await response(scope, replay_receive, send)
                if record.state == "DONE" and record.response_body:
                    response = _json_response(
                        record.status_code or 200,
                        json.loads(record.response_body),
                        {"Idempotent-Replayed": "true"},
                    )
                    return await response(scope, replay_receive, send)
                response = _json_response(
                    409,
                    {"code": "IDEMPOTENCY_IN_PROGRESS", "message": "相同请求标识正在处理中，请稍后重试"},
                )
                return await response(scope, replay_receive, send)

            db.add(
                IdempotencyRecord(
                    request_id=key,
                    user_id=user_id,
                    method=method,
                    path=path,
                    request_hash=digest,
                    state="PROCESSING",
                    expires_at=datetime.now() + timedelta(seconds=settings.idempotency_ttl_s),
                )
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                response = _json_response(
                    409,
                    {"code": "IDEMPOTENCY_IN_PROGRESS", "message": "相同请求标识正在处理中，请稍后重试"},
                )
                return await response(scope, replay_receive, send)

        captured = {"status": 500, "content_type": ""}
        chunks: list[bytes] = []

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                for name, value in message.get("headers", []):
                    if name.lower() == b"content-type":
                        captured["content_type"] = value.decode("latin-1")
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, replay_receive, send_wrapper)
        except Exception:
            _drop(key)
            raise
        _finish(key, captured["status"], b"".join(chunks), captured["content_type"])
