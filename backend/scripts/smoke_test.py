"""接口冒烟测试：鉴权、幂等、分页、参数校验、RBAC。

运行：python scripts/smoke_test.py
使用临时 SQLite 数据库，不依赖 MySQL / Docker。
"""
import os
import tempfile
import uuid
from pathlib import Path

DB_PATH = Path(tempfile.gettempdir()) / f"travel-smoke-{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
os.environ["AUTO_CREATE_TABLES"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def new_key() -> str:
    return uuid.uuid4().hex


def main() -> None:
    passed: list[str] = []
    with TestClient(app) as client:
        login_key = new_key()
        body = {"open_id": "smoke-user", "nickname": "冒烟测试", "source": "APP"}
        first = client.post("/api/v1/users/login", json=body, headers={"Idempotency-Key": login_key})
        assert first.status_code == 200, first.text
        token = first.json()["access_token"]
        assert first.json()["role"] == "USER"
        passed.append("登录签发 Bearer 令牌")

        replay = client.post("/api/v1/users/login", json=body, headers={"Idempotency-Key": login_key})
        assert replay.status_code == 200 and replay.headers.get("Idempotent-Replayed") == "true"
        passed.append("同一 Idempotency-Key 回放首次响应")

        missing_key = client.post("/api/v1/users/login", json=body)
        assert missing_key.status_code == 422 and missing_key.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"
        passed.append("写操作缺少请求标识被拒绝")

        auth = {"Authorization": f"Bearer {token}"}
        no_token = client.get("/api/v1/conversations", params={"user_id": 1})
        assert no_token.status_code == 401 and no_token.json()["code"] == "UNAUTHORIZED"
        passed.append("未携带令牌返回 401")

        create_headers = {**auth, "Idempotency-Key": new_key()}
        created = client.post("/api/v1/conversations", json={"user_id": first.json()["id"]}, headers=create_headers)
        assert created.status_code == 200, created.text
        conversation_id = created.json()["id"]
        passed.append("创建会话")

        listing = client.get("/api/v1/conversations", params={"page": 1, "page_size": 5, "sort": "id:desc"}, headers=auth)
        assert listing.status_code == 200
        payload = listing.json()
        assert {"items", "total", "page", "page_size"} <= payload.keys()
        passed.append("会话列表返回分页包裹")

        bad_sort = client.get("/api/v1/conversations", params={"sort": "open_id:desc"}, headers=auth)
        assert bad_sort.status_code == 422 and bad_sort.json()["code"] == "VALIDATION_ERROR"
        passed.append("非白名单排序字段返回 422")

        pois = client.get("/api/v1/resources/pois", params={"page": 1, "page_size": 10}, headers=auth)
        assert pois.status_code == 200 and "items" in pois.json()
        passed.append("景点列表分页")

        forbidden = client.get("/api/v1/tool-logs", headers=auth)
        assert forbidden.status_code == 403 and forbidden.json()["code"] == "FORBIDDEN"
        passed.append("USER 访问 ADMIN 接口返回 403")

        bad_body = client.post(
            f"/api/v1/trips/{conversation_id}/items",
            json={"day_index": 1, "start_time": "9:00", "end_time": "10:00", "ref_name": "测试"},
            headers={**auth, "Idempotency-Key": new_key()},
        )
        assert bad_body.status_code == 422 and bad_body.json()["code"] == "VALIDATION_ERROR"
        assert bad_body.json()["errors"][0]["field"].startswith("body")
        passed.append("请求体参数校验返回统一错误结构")

        other = client.post(
            "/api/v1/users/login",
            json={"open_id": "other-user"},
            headers={"Idempotency-Key": new_key()},
        ).json()
        other_auth = {"Authorization": f"Bearer {other['access_token']}"}
        cross = client.get(f"/api/v1/conversations/{conversation_id}", headers=other_auth)
        assert cross.status_code == 403 and cross.json()["code"] == "FORBIDDEN"
        passed.append("跨用户访问他人会话被拒绝")

    for item in passed:
        print(f"[PASS] {item}")
    print(f"\n全部 {len(passed)} 项检查通过，临时库：{DB_PATH}")


if __name__ == "__main__":
    try:
        main()
    finally:
        from app.common.db import engine

        engine.dispose()
        if DB_PATH.exists():
            try:
                DB_PATH.unlink()
            except PermissionError:
                pass
