from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, data_scopes, depts, groups, logs, privileges, users
from app.common.config import settings
from app.common.db import init_db
from app.common.errors import (
    AppError,
    app_error_handler,
    http_error_handler,
    validation_error_handler,
)
from app.seed import seed_initial_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        init_db()
    if settings.seed_on_start:
        seed_initial_data()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="参照禅道 RBAC 权限模型实现的用户 / 部门 / 用户组 / 组权限 / 数据范围 / 操作日志服务。",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*" else [o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

for module in (auth, users, depts, groups, privileges, data_scopes, logs):
    app.include_router(module.router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "env": settings.app_env, "api": settings.api_prefix}
