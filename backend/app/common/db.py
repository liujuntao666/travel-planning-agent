from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.common.config import settings


def _engine_kwargs(url: str) -> dict:
    kwargs: dict = {"pool_pre_ping": True, "future": True, "echo": settings.db_echo}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """开发环境下自动建表；生产环境建议直接执行 deploy/mysql/init 下的脚本。"""
    if not settings.auto_create_tables or settings.database_url.startswith("sqlite"):
        if settings.database_url.startswith("sqlite"):
            import app.models  # noqa: F401  确保模型注册
            from app.models.base import Base

            Base.metadata.create_all(bind=engine)
        return

    import app.models  # noqa: F401
    from app.models.base import Base

    Base.metadata.create_all(bind=engine)
