from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务异常：携带错误码与 HTTP 状态码，统一转换为 JSON。"""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class UnauthorizedError(AppError):
    def __init__(self, message: str = "未登录或令牌失效") -> None:
        super().__init__("UNAUTHORIZED", message, 401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "无权限访问该资源") -> None:
        super().__init__("FORBIDDEN", message, 403)


class LockedError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("LOCKED", message, 403)


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__("NOT_FOUND", message, 404)


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("CONFLICT", message, 409)


class ValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("VALIDATION_ERROR", message, 422)


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": f"HTTP_{exc.status_code}", "message": exc.detail},
    )


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    msg = first.get("msg", "参数校验失败")
    message = f"{loc}: {msg}" if loc else msg
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": message},
    )
