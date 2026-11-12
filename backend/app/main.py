from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.agent_core.llm import llm_client
from app.api import admin, auth, conversations, resources, trips, users
from app.common.auth_middleware import AuthMiddleware
from app.common.config import settings
from app.common.db import engine, init_db
from app.common.errors import AppError, app_error_handler, http_error_handler
from app.common.idempotency import IdempotencyMiddleware
from app.common.logging import setup_logging
from app.common.redis_client import redis_backend
from app.common.seed import seed_rbac


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    seed_rbac()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="基于大模型与智能体的个性化旅行规划系统（C 端）：一句话生成行程、多轮调整、编辑重排、一键导出。",
    lifespan=lifespan,
)

app.add_middleware(IdempotencyMiddleware)
# 注册顺序决定执行顺序：后注册的在外层，CORS 必须最外层以覆盖 401 响应
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


FIELD_LABELS = {
    "username": "用户名",
    "password": "密码",
    "new_password": "新密码",
    "nickname": "昵称",
    "email": "邮箱",
    "phone": "手机号",
    "account": "账号",
    "captcha_id": "验证码标识",
    "captcha_code": "图形验证码",
    "reset_token": "重置凭证",
}

FIELD_HINTS = {
    "username": "用户名需为 3-32 位字母、数字或下划线",
    "password": "密码需 8-64 位且同时包含字母与数字",
    "new_password": "新密码需 8-64 位且同时包含字母与数字",
    "email": "请输入正确的邮箱地址，例如 name@example.com",
    "phone": "手机号需为 6-20 位数字，可带 + 前缀",
}


def _describe_validation_error(item: dict) -> dict:
    loc = [str(part) for part in item.get("loc", []) if part not in ("body", "query", "path")]
    field = ".".join(loc)
    label = FIELD_LABELS.get(field, field or "参数")
    err_type = str(item.get("type", ""))
    ctx = item.get("ctx") or {}

    if err_type == "missing":
        message = f"缺少必填参数：{label}"
    elif err_type == "string_pattern_mismatch":
        message = FIELD_HINTS.get(field, f"{label}格式不正确")
    elif err_type == "string_too_short":
        message = f"{label}至少需要 {ctx.get('min_length')} 个字符"
    elif err_type == "string_too_long":
        message = f"{label}不能超过 {ctx.get('max_length')} 个字符"
    elif err_type == "value_error":
        message = str(item.get("msg", "")).replace("Value error, ", "")
    elif err_type in ("int_parsing", "bool_parsing", "float_parsing"):
        message = f"{label}需要填写数字"
    else:
        message = f"{label}不合法"

    return {"field": field or "body", "label": label, "message": message}


async def validation_error_handler(_: object, exc: RequestValidationError) -> JSONResponse:
    errors = [_describe_validation_error(item) for item in exc.errors()]
    # 顶层 message 直接给出第一条可操作的原因，避免前端只看到笼统的“参数校验失败”
    message = errors[0]["message"] if errors else "参数校验失败"
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": message, "errors": errors},
    )


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

settings.export_dir.mkdir(parents=True, exist_ok=True)
app.mount(settings.static_mount, StaticFiles(directory=settings.export_dir), name="static")

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(conversations.router, prefix=settings.api_prefix)
app.include_router(trips.router, prefix=settings.api_prefix)
app.include_router(resources.router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict:
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "redis": redis_backend(),
        "llm": "configured" if llm_client.enabled else "rule-engine",
        "tool_timeout_ms": settings.tool_timeout_ms,
        "env": settings.app_env,
    }


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/health",
        "api": settings.api_prefix,
    }
