from tests.conftest import auth, login

PWD = "e10adc3949ba59abbe56e057f20f883e"


def test_product_scope_personal_view(client, dev_token):
    response = client.get("/api/v1/data-scopes/products", headers=auth(dev_token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["product_id"] for item in items] == [1, 2, 3]
    assert {item["product_id"]: item["granted"] for item in items} == {1: True, 2: True, 3: False}
    assert items[0]["acl_open"] is True


def test_project_scope_personal_view(client, dev_token):
    response = client.get("/api/v1/data-scopes/projects", headers=auth(dev_token))
    assert response.status_code == 200
    assert {item["project_id"]: item["granted"] for item in response.json()["items"]} == {
        1: True,
        2: False,
        3: False,
    }


def test_set_scope_requires_admin_for_others_and_affects_me(client, admin_token, dev_token):
    # zhangsan 仅有 data-view，无 data-edit，不能为自己或他人设置
    forbidden = client.put(
        "/api/v1/data-scopes/products",
        headers=auth(dev_token),
        json={"account": "lisi", "product_ids": [1]},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["message"] == "无权限：data-edit"

    # 超级管理员为 zhangsan 设置项目白名单后，其可见数据范围立即变化
    granted = client.put(
        "/api/v1/data-scopes/projects",
        headers=auth(admin_token),
        json={"account": "zhangsan", "project_ids": [1, 3]},
    )
    assert granted.status_code == 200
    assert granted.json()["count"] == 2
    me = client.get("/api/v1/auth/me", headers=auth(dev_token)).json()
    assert me["data_scope"]["projects"] == [1, 3]

    restored = client.put(
        "/api/v1/data-scopes/projects",
        headers=auth(admin_token),
        json={"account": "zhangsan", "project_ids": [1]},
    )
    assert restored.json()["count"] == 1
    assert client.get("/api/v1/auth/me", headers=auth(dev_token)).json()["data_scope"]["projects"] == [1]

    admin_view = client.get(
        "/api/v1/data-scopes/products", headers=auth(admin_token), params={"account": "lisi"}
    )
    assert admin_view.status_code == 200
    assert len(admin_view.json()["items"]) == 3

    invalid = client.put(
        "/api/v1/data-scopes/products", headers=auth(admin_token), json={"product_ids": [999]}
    )
    assert invalid.status_code == 422


def test_admin_scope_is_full(client, admin_token):
    me = client.get("/api/v1/auth/me", headers=auth(admin_token)).json()
    assert me["data_scope"] == {"products": [1, 2, 3], "projects": [1, 2, 3]}
    assert "user-delete" in me["privileges"]
    assert len(me["privileges"]) == 26


def test_menus_filtered_by_privileges(client, dev_token):
    menus = client.get("/api/v1/menus", headers=auth(dev_token))
    assert menus.status_code == 200
    assert [item["id"] for item in menus.json()["menus"]] == [
        "user", "dept", "group", "privilege", "data", "log",
    ]

    qa_token = login(client, "wangwu", PWD)["token"]
    qa_menus = client.get("/api/v1/menus", headers=auth(qa_token))
    assert [item["id"] for item in qa_menus.json()["menus"]] == ["user", "dept", "data", "log"]


def test_privileges_module_list(client, admin_token):
    response = client.get("/api/v1/privileges", headers=auth(admin_token))
    assert response.status_code == 200
    modules = response.json()["modules"]
    assert [module["module"] for module in modules] == [
        "user", "dept", "group", "privilege", "data", "log",
    ]
    assert len(modules[0]["methods"]) == 8
    assert modules[0]["name"] == "用户管理"

    filtered = client.get("/api/v1/privileges", headers=auth(admin_token), params={"module": "log"})
    assert [module["module"] for module in filtered.json()["modules"]] == ["log"]

    qa_token = login(client, "wangwu", PWD)["token"]
    denied = client.get("/api/v1/privileges", headers=auth(qa_token))
    assert denied.status_code == 403
    assert denied.json() == {"code": "FORBIDDEN", "message": "无权限：privilege-browse"}


def test_logs_paging_filter_and_masking(client, admin_token):
    response = client.get(
        "/api/v1/logs", headers=auth(admin_token), params={"module": "auth", "page_size": 5}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"total", "page", "page_size", "items"}
    assert body["total"] >= 1
    assert body["items"][0]["module"] == "auth"
    assert body["items"][0]["created_at"]

    fail_only = client.get(
        "/api/v1/logs", headers=auth(admin_token), params={"result": "FAIL", "account": "sunqi"}
    )
    assert fail_only.json()["total"] == 6

    login_log = client.get(
        "/api/v1/logs", headers=auth(admin_token),
        params={"module": "auth", "method": "login", "result": "SUCCESS"},
    ).json()
    log_id = login_log["items"][0]["id"]
    detail = client.get(f"/api/v1/logs/{log_id}", headers=auth(admin_token))
    assert detail.status_code == 200
    assert detail.json()["params"]["password"] == "***"
    assert detail.json()["ip"]

    missing = client.get("/api/v1/logs/999999", headers=auth(admin_token))
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"
