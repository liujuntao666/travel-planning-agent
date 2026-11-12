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

    # 鉴权（HMAC-SHA256 签名令牌 + Redis 会话）
    auth_secret: str = "travel-planning-dev-secret-change-me"
    auth_token_ttl_s: int = 7200
    authz_cache_ttl_s: int = 300
    allow_open_id_login: bool = True

    # Redis：会话、验证码、限流、权限与字典缓存
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_required: bool = False

    # 登录安全
    captcha_ttl_s: int = 120
    captcha_debug: bool = False  # 仅联调/自动化测试：验证码响应附带明文答案
    login_max_failures: int = 5
    login_lock_s: int = 900
    login_rate_limit: int = 10
    login_rate_window_s: int = 60
    register_rate_limit: int = 5
    register_rate_window_s: int = 3600
    password_iterations: int = 200_000
    password_reset_ttl_s: int = 600

    # 初始化账号（首次启动自动创建，生产环境请立即修改密码）
    seed_rbac: bool = True
    seed_admin_username: str = "admin"
    seed_admin_password: str = "Admin@123456"
    seed_demo_username: str = "traveler"
    seed_demo_password: str = "Traveler@123456"

    # 幂等控制
    idempotency_ttl_s: int = 86400

    # 列表分页
    default_page_size: int = 20
    max_page_size: int = 100

    # 导出
    export_dir: Path = BASE_DIR / "var" / "exports"
    static_mount: str = "/static"

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
