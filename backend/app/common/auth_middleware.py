"""接口拦截：统一校验 Bearer 令牌与 Redis 会话，等价于安全框架的过滤链。"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.common.auth_session import get_session
from app.common.config import settings
from app.common.errors import UnauthorizedError
from app.common.security import decode_token

WHITELIST = {
    "/health",
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
    f"{settings.api_prefix}/auth/captcha",
    f"{settings.api_prefix}/auth/register",
    f"{settings.api_prefix}/auth/login",
    f"{settings.api_prefix}/auth/password/forgot",
    f"{settings.api_prefix}/auth/password/reset",
    f"{settings.api_prefix}/users/login",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or not path.startswith(settings.api_prefix):
            return await call_next(request)
        if path in WHITELIST:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return _unauthorized("缺少访问令牌")
        token = authorization[7:].strip()
        try:
            payload = decode_token(token)
        except UnauthorizedError as exc:
            return _unauthorized(exc.message)
        session = get_session(token)
        if not session or int(session.get("user_id", 0)) != int(payload.get("sub", 0)):
            return _unauthorized("登录会话已失效，请重新登录")
        request.state.user_id = int(payload.get("sub", 0))
        request.state.role = payload.get("role")
        return await call_next(request)


def _unauthorized(message: str) -> JSONResponse:
    return JSONResponse(status_code=401, content={"code": "UNAUTHORIZED", "message": message})
