"""导出 OpenAPI 3.1 描述文件，供 Apifox / Postman 导入。"""
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.common.idempotency import EXEMPT_PATHS  # noqa: E402
from app.main import app  # noqa: E402

ARTIFACTS_DIR = Path(
    os.environ.get("ARTIFACTS_DIR", PROJECT_DIR.parent / "travel-planning-agent-artifacts")
)
TARGET = ARTIFACTS_DIR / "api-reference" / "openapi.json"
MUTATING = {"post", "put", "patch", "delete"}
EXEMPT = set(EXEMPT_PATHS) | {"/api/v1/conversations/{conversation_id}/messages/stream"}


def _inject_idempotency(schema: dict) -> None:
    for path, methods in schema.get("paths", {}).items():
        if path in EXEMPT:
            continue
        for method, operation in methods.items():
            if method not in MUTATING:
                continue
            params = operation.setdefault("parameters", [])
            if any(p.get("name") == "Idempotency-Key" for p in params):
                continue
            params.append(
                {
                    "name": "Idempotency-Key",
                    "in": "header",
                    "required": True,
                    "description": "唯一请求标识，1–64 字符，建议 UUID；重复提交相同标识会回放首次成功响应",
                    "schema": {"type": "string", "maxLength": 64},
                }
            )


def main() -> None:
    schema = app.openapi()
    _inject_idempotency(schema)
    schema.setdefault("servers", []).extend(
        [
            {"url": "http://localhost:8001", "description": "后端直连（Docker 端口映射）"},
            {"url": "http://localhost:8080", "description": "C 端前端 Nginx 代理"},
            {"url": "http://localhost:8081", "description": "管理后台 Nginx 代理"},
        ]
    )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAPI 已导出：{TARGET}")
    print(f"路径数量：{len(schema.get('paths', {}))}")


if __name__ == "__main__":
    main()
