from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置，全部可通过环境变量覆盖（见 deploy/.env.example）。"""

    app_name: str = "旅游规划智能体系统"
    app_env: str = "dev"
    api_prefix: str = "/api/v1"
    cors_origins: str = "*"

    # 数据库：默认对齐《数据库设计说明书》的 MySQL 8.0
    database_url: str = (
        "mysql+pymysql://travel:travel_dev@127.0.0.1:3306/travel_planning?charset=utf8mb4"
    )
    db_echo: bool = False
    auto_create_tables: bool = True

    # 大模型（OpenAI 兼容协议）；未配置 key 时使用确定性规则引擎
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_s: float = 20.0

    # 外部工具
    tool_timeout_ms: int = 5000
    tool_offline: bool = False  # 置 true 可做故障注入演练（NFR-05）

    # 行程
    default_start_offset_days: int = 7
    max_day_count: int = 15
    max_people: int = 20

    # 导出
    export_dir: Path = BASE_DIR / "var" / "exports"
    static_mount: str = "/static"

    # 文件上传与下载
    file_dir: Path = BASE_DIR / "var" / "files"
    chunk_dir: Path = BASE_DIR / "var" / "chunks"
    chunk_size: int = 5 * 1024 * 1024
    max_upload_size: int = 2 * 1024 * 1024 * 1024
    max_batch_files: int = 50
    max_batch_file_size: int = 50 * 1024 * 1024
    download_block_size: int = 1024 * 1024
    # 由 Nginx 直接发送文件（X-Accel-Redirect），避免 Python 成为下载瓶颈
    nginx_accel: bool = False
    nginx_accel_prefix: str = "/_files/"

    model_config = SettingsConfigDict(
        env_file=(".env", "../deploy/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
