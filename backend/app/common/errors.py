from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务异常：携带错误码与 HTTP 状态码，统一转换为 JSON。"""

    def __init__(self, code: str, message: str, status_code: int = 400,
                 data: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data


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
    content: dict = {"code": exc.code, "message": exc.message}
    if exc.data:
        content.update(exc.data)
    return JSONResponse(status_code=exc.status_code, content=content)


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": f"HTTP_{exc.status_code}", "message": exc.detail},
    )
