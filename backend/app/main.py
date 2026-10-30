from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.agent_core.llm import llm_client
from app.api import conversations, files, resources, trips, users
from app.common.config import settings
from app.common.db import engine, init_db
from app.common.errors import AppError, app_error_handler, http_error_handler
from app.common.logging import setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    settings.file_dir.mkdir(parents=True, exist_ok=True)
    settings.chunk_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="基于大模型与智能体的个性化旅行规划系统（C 端）：一句话生成行程、多轮调整、编辑重排、一键导出。",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)

settings.export_dir.mkdir(parents=True, exist_ok=True)
app.mount(settings.static_mount, StaticFiles(directory=settings.export_dir), name="static")

app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(conversations.router, prefix=settings.api_prefix)
app.include_router(trips.router, prefix=settings.api_prefix)
app.include_router(resources.router, prefix=settings.api_prefix)
app.include_router(files.router, prefix=settings.api_prefix)


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
