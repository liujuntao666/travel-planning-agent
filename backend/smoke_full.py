"""临时冒烟脚本：登录链路、RBAC 管理接口、缓存与限流。"""
import secrets

from fastapi.testclient import TestClient

from app.main import app


class IdemClient(TestClient):
    """写操作自动补 Idempotency-Key，避免逐个接口手写。"""

    def request(self, method, url, **kwargs):
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            headers = dict(kwargs.get("headers") or {})
            headers.setdefault("Idempotency-Key", secrets.token_hex(16))
            kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


def captcha(client: TestClient) -> dict:
    data = client.get("/api/v1/auth/captcha").json()
    return {"captcha_id": data["captcha_id"], "captcha_code": data["debug_code"]}


def login(client: TestClient, username: str, password: str) -> dict:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, **captcha(client)},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


with IdemClient(app) as client:
    admin = login(client, "admin", "Admin@123456")
    token = admin["access_token"]
    ah = {"Authorization": f"Bearer {token}"}
    print("admin perms:", len(admin["permissions"]), "menus:", len(admin["menus"]))

    # 角色
    roles = client.get("/api/v1/admin/roles", headers=ah, params={"page_size": 50})
    assert roles.status_code == 200, roles.text
    print("roles total:", roles.json()["total"])

    created = client.post(
        "/api/v1/admin/roles",
        headers=ah,
        json={"role_code": "SMOKE2", "role_name": "冒烟角色2"},
    )
    assert created.status_code == 200, created.text
    role_id = created.json()["id"]

    menus = client.get("/api/v1/admin/menus", headers=ah, params={"page_size": 100})
    perms = client.get("/api/v1/admin/permissions", headers=ah, params={"page_size": 100})
    menu_ids = [m["id"] for m in menus.json()["items"]][:3]
    perm_ids = [p["id"] for p in perms.json()["items"]][:2]

    g1 = client.put(f"/api/v1/admin/roles/{role_id}/menus", headers=ah, json={"menu_ids": menu_ids})
    g2 = client.put(
        f"/api/v1/admin/roles/{role_id}/permissions", headers=ah, json={"permission_ids": perm_ids}
    )
    grants = client.get(f"/api/v1/admin/roles/{role_id}/grants", headers=ah)
    print("grant menus:", g1.status_code, "perms:", g2.status_code, "grants:", grants.json())

    # 菜单 / 权限 CRUD
    new_menu = client.post(
        "/api/v1/admin/menus",
        headers=ah,
        json={"menu_code": "smoke_menu", "menu_name": "冒烟菜单", "path": "/smoke", "sort_no": 99},
    )
    assert new_menu.status_code == 200, new_menu.text
    menu_id = new_menu.json()["id"]
    patched = client.patch(
        f"/api/v1/admin/menus/{menu_id}", headers=ah, json={"menu_name": "冒烟菜单改"}
    )
    deleted = client.delete(f"/api/v1/admin/menus/{menu_id}", headers=ah)
    print("menu crud:", new_menu.status_code, patched.status_code, deleted.status_code)

    new_perm = client.post(
        "/api/v1/admin/permissions",
        headers=ah,
        json={"perm_code": "smoke:read", "perm_name": "冒烟权限", "resource": "smoke", "method": "GET"},
    )
    assert new_perm.status_code == 200, new_perm.text
    perm_id = new_perm.json()["id"]
    print("perm method upper:", new_perm.json()["method"])

    # 注册用户并分配角色
    username = f"u{secrets.token_hex(3)}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "Passw0rd123", **captcha(client)},
    )
    assert reg.status_code == 200, reg.text
    user_id = reg.json()["user"]["id"]
    user_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    before = client.get("/api/v1/admin/roles", headers=user_headers)
    assigned = client.put(
        f"/api/v1/admin/users/{user_id}/roles", headers=ah, json={"role_ids": [role_id]}
    )
    print("user before grant:", before.status_code, "assign:", assigned.status_code)
    # 分配角色会撤销该用户会话
    revoked = client.get("/api/v1/auth/me", headers=user_headers)
    print("session revoked after grant:", revoked.status_code)

    authz = client.get(f"/api/v1/admin/users/{user_id}/authz", headers=ah)
    print("authz after grant:", authz.status_code, authz.json()["roles"], len(authz.json()["permissions"]))

    users = client.get("/api/v1/admin/users", headers=ah, params={"page_size": 20, "role_code": "SMOKE2"})
    print("users filter:", users.status_code, users.json()["total"])

    # 清理
    client.delete(f"/api/v1/admin/permissions/{perm_id}", headers=ah)
    client.delete(f"/api/v1/admin/roles/{role_id}", headers=ah)
    after_delete = client.get(f"/api/v1/admin/users/{user_id}/authz", headers=ah)
    print("authz after role delete:", after_delete.json()["roles"], len(after_delete.json()["permissions"]))
    assert "SMOKE2" not in after_delete.json()["roles"]

    # 缓存接口
    cities = client.get("/api/v1/resources/cities", headers=ah)
    dicts = client.get("/api/v1/meta/dictionaries", headers=ah)
    print("cities:", cities.status_code, "dicts:", dicts.status_code)

    # C 端 OpenID 登录（多登录方式）
    open_login = client.post("/api/v1/users/login", json={"open_id": "smoke-openid-1", "source": "APP"})
    assert open_login.status_code == 200, open_login.text
    open_headers = {"Authorization": f"Bearer {open_login.json()['access_token']}"}
    trips_read = client.get("/api/v1/resources/cities", headers=open_headers)
    print("openid login perms:", len(open_login.json()["permissions"]), "resource read:", trips_read.status_code)

    # 忘记密码 → 重置 → 新密码登录（重置凭证一次性）
    forgot = client.post("/api/v1/auth/password/forgot", json={"account": username, **captcha(client)})
    assert forgot.status_code == 200, forgot.text
    reset_token = forgot.json()["reset_token"]
    assert reset_token, forgot.text
    reset = client.post(
        "/api/v1/auth/password/reset",
        json={"reset_token": reset_token, "new_password": "NewPass123"},
    )
    assert reset.status_code == 200, reset.text
    reused = client.post(
        "/api/v1/auth/password/reset",
        json={"reset_token": reset_token, "new_password": "NewPass123"},
    )
    print("reset reused token:", reused.status_code)
    relogin = login(client, username, "NewPass123")
    print("login with new password ok:", relogin["user"]["username"])

    # 登录失败锁定：连续错误 5 次后即使密码正确也拒绝
    from app.common.ratelimit import clear_login_failures

    for _ in range(5):
        bad = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "WrongPass1", **captcha(client)},
        )
    locked = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "NewPass123", **captcha(client)},
    )
    print("locked after 5 failures:", bad.status_code, locked.status_code, locked.json().get("message"))
    assert locked.status_code == 401
    clear_login_failures(username, "testclient")

    # 接口限流：同一 IP 超过窗口阈值返回 429
    codes = []
    for _ in range(12):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "Whatever1", **captcha(client)},
        )
        codes.append(resp.status_code)
    print("rate limit codes:", codes)
    assert 429 in codes

    print("ALL OK")
