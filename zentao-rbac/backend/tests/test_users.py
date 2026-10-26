from tests.conftest import auth, login

PWD = "e10adc3949ba59abbe56e057f20f883e"
NEW_PWD = "25d55ad283aa400af464c76d713c07ad"


def test_create_user_and_conflicts(client, admin_token):
    payload = {
        "account": "newdev",
        "realname": "新同学",
        "password": PWD,
        "dept_id": 3,
        "role": "dev",
        "email": "newdev@example.com",
        "group_ids": [1],
    }
    created = client.post("/api/v1/users", headers=auth(admin_token), json=payload)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["account"] == "newdev"
    assert body["id"] > 0

    duplicated = client.post("/api/v1/users", headers=auth(admin_token), json=payload)
    assert duplicated.status_code == 409
    assert duplicated.json()["code"] == "CONFLICT"

    bad_account = client.post(
        "/api/v1/users", headers=auth(admin_token), json={**payload, "account": "a"}
    )
    assert bad_account.status_code == 422
    assert bad_account.json()["code"] == "VALIDATION_ERROR"

    bad_group = client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={**payload, "account": "newdev2", "group_ids": [999]},
    )
    assert bad_group.status_code == 422


def test_list_users_filter_and_paging(client, admin_token, dev_token):
    response = client.get(
        "/api/v1/users", headers=auth(admin_token), params={"keyword": "张", "page": 1, "page_size": 10}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"total", "page", "page_size", "items"}
    assert [item["account"] for item in body["items"]] == ["zhangsan"]
    assert body["items"][0]["dept_name"] == "研发部"

    by_group = client.get("/api/v1/users", headers=auth(admin_token), params={"group_id": 2})
    assert [item["account"] for item in by_group.json()["items"]] == ["wangwu"]

    by_dept = client.get("/api/v1/users", headers=auth(admin_token), params={"dept_id": 2})
    accounts = {item["account"] for item in by_dept.json()["items"]}
    assert {"zhangsan", "lisi", "wangwu"} <= accounts

    by_sub_dept = client.get("/api/v1/users", headers=auth(admin_token), params={"dept_id": 4})
    assert [item["account"] for item in by_sub_dept.json()["items"]] == ["wangwu"]

    # 未加入任何用户组的账号不具备 user-browse，列表接口返回 403
    assert client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={"account": "nogroup1", "realname": "无组用户", "password": PWD, "dept_id": 3, "role": "dev"},
    ).status_code == 200
    nogroup_token = login(client, "nogroup1", PWD)["token"]
    denied = client.get("/api/v1/users", headers=auth(nogroup_token))
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"
    assert client.delete("/api/v1/users/nogroup1", headers=auth(admin_token)).status_code == 200


def test_user_detail_permission(client, admin_token, dev_token):
    mine = client.get("/api/v1/users/zhangsan", headers=auth(dev_token))
    assert mine.status_code == 200
    assert mine.json()["dept_name"] == "研发部"
    assert "user-browse" in mine.json()["privileges"]

    others = client.get("/api/v1/users/wangwu", headers=auth(dev_token))
    assert others.status_code == 403

    admin_view = client.get("/api/v1/users/wangwu", headers=auth(admin_token))
    assert admin_view.status_code == 200
    assert admin_view.json()["account"] == "wangwu"

    missing = client.get("/api/v1/users/ghost", headers=auth(admin_token))
    assert missing.status_code == 404


def test_group_privilege_change_takes_effect(client, admin_token, dev_token):
    created = client.post(
        "/api/v1/groups",
        headers=auth(admin_token),
        json={"name": "临时-编辑组", "role": "pm", "desc": "用于验证权限实时生效"},
    )
    assert created.status_code == 200
    group_id = created.json()["id"]

    patch_body = {"realname": "张三"}
    before = client.patch("/api/v1/users/zhangsan", headers=auth(dev_token), json=patch_body)
    assert before.status_code == 403

    assert client.put(
        f"/api/v1/users/zhangsan/groups", headers=auth(admin_token), json={"group_ids": [1, group_id]}
    ).status_code == 200
    assert client.put(
        f"/api/v1/groups/{group_id}/privileges", headers=auth(admin_token), json={"privileges": ["user-edit"]}
    ).status_code == 200

    after = client.patch("/api/v1/users/zhangsan", headers=auth(dev_token), json=patch_body)
    assert after.status_code == 200, after.text

    assert client.put(
        f"/api/v1/groups/{group_id}/privileges", headers=auth(admin_token), json={"privileges": []}
    ).json()["count"] == 0

    revoked = client.patch("/api/v1/users/zhangsan", headers=auth(dev_token), json=patch_body)
    assert revoked.status_code == 403

    # 还原成员关系并清理临时组
    assert client.put(
        "/api/v1/users/zhangsan/groups", headers=auth(admin_token), json={"group_ids": [1]}
    ).json()["groups"][0]["id"] == 1
    assert client.delete(
        f"/api/v1/groups/{group_id}", headers=auth(admin_token), params={"force": True}
    ).status_code == 200


def test_update_last_admin_and_delete_rules(client, admin_token):
    demote = client.patch(
        "/api/v1/users/admin", headers=auth(admin_token), json={"admin": "no"}
    )
    assert demote.status_code == 409

    delete_self = client.delete("/api/v1/users/admin", headers=auth(admin_token))
    assert delete_self.status_code == 409

    assert client.post(
        "/api/v1/users/newdev/unlock", headers=auth(admin_token)
    ).status_code == 200

    assert client.delete("/api/v1/users/newdev", headers=auth(admin_token)).status_code == 200
    assert client.get("/api/v1/users/newdev", headers=auth(admin_token)).status_code == 404


def test_reset_password_revokes_tokens(client, admin_token):
    assert client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={"account": "temp1", "realname": "临时", "password": PWD, "dept_id": 3, "role": "dev"},
    ).status_code == 200
    token = login(client, "temp1", PWD)["token"]
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200

    reset = client.post(
        "/api/v1/users/temp1/reset-password", headers=auth(admin_token), json={"new_password": NEW_PWD}
    )
    assert reset.status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401
    assert login(client, "temp1", NEW_PWD)["user"]["account"] == "temp1"
    assert client.delete("/api/v1/users/temp1", headers=auth(admin_token)).status_code == 200
