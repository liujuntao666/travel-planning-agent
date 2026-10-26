from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """服务配置，全部可通过环境变量覆盖（见 .env.example）。"""

    app_name: str = "仿禅道项目管理系统 RBAC 权限服务"
    app_env: str = "dev"
    api_prefix: str = "/api/v1"
    cors_origins: str = "*"

    # 默认对齐文档：MySQL 8.0；测试使用 SQLite
    database_url: str = (
        "mysql+pymysql://rbac:rbac_dev@127.0.0.1:3306/zentao_rbac?charset=utf8mb4"
    )
    db_echo: bool = False
    auto_create_tables: bool = True
    seed_on_start: bool = True

    # 令牌
    token_ttl_seconds: int = 7200
    remember_ttl_seconds: int = 604800

    # 登录锁定策略
    login_max_fails: int = 5
    login_lock_minutes: int = 10

    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
