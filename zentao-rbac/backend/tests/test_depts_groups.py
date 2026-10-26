from tests.conftest import auth


def test_dept_tree_and_counts(client, admin_token):
    response = client.get("/api/v1/depts/tree", headers=auth(admin_token), params={"with_users": True})
    assert response.status_code == 200
    tree = response.json()["tree"]
    assert len(tree) == 1
    root = tree[0]
    assert root["name"] == "总公司"
    assert root["path"] == ",1,"
    assert root["user_count"] == 1

    dev_center = next(node for node in root["children"] if node["id"] == 2)
    dev_dept = next(node for node in dev_center["children"] if node["id"] == 3)
    assert dev_dept["path"] == ",1,2,3,"
    assert dev_dept["user_count"] == 2


def test_create_dept_and_duplicate(client, admin_token):
    created = client.post(
        "/api/v1/depts",
        headers=auth(admin_token),
        json={"name": "前端组", "parent_id": 3, "manager": "zhangsan", "position": 10},
    )
    assert created.status_code == 200
    dept_id = created.json()["id"]

    tree = client.get("/api/v1/depts/tree", headers=auth(admin_token)).json()["tree"]
    dev_dept = next(n for n in next(n for n in tree[0]["children"] if n["id"] == 2)["children"] if n["id"] == 3)
    node = next(child for child in dev_dept["children"] if child["id"] == dept_id)
    assert node["path"] == ",1,2,3,%d," % dept_id
    assert node["manager"] == "zhangsan"

    duplicated = client.post(
        "/api/v1/depts", headers=auth(admin_token), json={"name": "前端组", "parent_id": 3}
    )
    assert duplicated.status_code == 409

    missing_parent = client.post(
        "/api/v1/depts", headers=auth(admin_token), json={"name": "孤儿组", "parent_id": 999}
    )
    assert missing_parent.status_code == 422

    assert client.patch(
        f"/api/v1/depts/{dept_id}", headers=auth(admin_token), json={"name": "前端开发组", "position": 5}
    ).status_code == 200
    assert client.delete(f"/api/v1/depts/{dept_id}", headers=auth(admin_token)).status_code == 200


def test_move_dept_syncs_descendants(client, admin_token):
    parent = client.post(
        "/api/v1/depts", headers=auth(admin_token), json={"name": "临时父部门", "parent_id": 1}
    ).json()["id"]
    child = client.post(
        "/api/v1/depts", headers=auth(admin_token), json={"name": "临时子部门", "parent_id": parent}
    ).json()["id"]

    to_self = client.put(
        f"/api/v1/depts/{parent}/move", headers=auth(admin_token), json={"parent_id": parent}
    )
    assert to_self.status_code == 409

    to_descendant = client.put(
        f"/api/v1/depts/{parent}/move", headers=auth(admin_token), json={"parent_id": child}
    )
    assert to_descendant.status_code == 409

    moved = client.put(
        f"/api/v1/depts/{parent}/move", headers=auth(admin_token), json={"parent_id": 2}
    )
    assert moved.status_code == 200

    tree = client.get("/api/v1/depts/tree", headers=auth(admin_token)).json()["tree"]
    dev_center = next(node for node in tree[0]["children"] if node["id"] == 2)
    moved_node = next(node for node in dev_center["children"] if node["id"] == parent)
    assert moved_node["path"] == ",1,2,%d," % parent
    assert moved_node["children"][0]["path"] == ",1,2,%d,%d," % (parent, child)

    assert client.delete(f"/api/v1/depts/{parent}", headers=auth(admin_token)).status_code == 409
    assert client.delete(f"/api/v1/depts/{child}", headers=auth(admin_token)).status_code == 200
    assert client.delete(f"/api/v1/depts/{parent}", headers=auth(admin_token)).status_code == 200


def test_delete_dept_with_users(client, admin_token):
    dept_id = client.post(
        "/api/v1/depts", headers=auth(admin_token), json={"name": "临时部门A", "parent_id": 1}
    ).json()["id"]
    target_dept = client.post(
        "/api/v1/depts", headers=auth(admin_token), json={"name": "临时部门B", "parent_id": 1}
    ).json()["id"]
    assert client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={"account": "deptuser", "realname": "部门用户", "password": "e10adc3949ba59abbe56e057f20f883e",
              "dept_id": dept_id, "role": "dev"},
    ).status_code == 200

    blocked = client.delete(f"/api/v1/depts/{dept_id}", headers=auth(admin_token))
    assert blocked.status_code == 409
    assert "迁入部门" in blocked.json()["message"]

    ok = client.delete(
        f"/api/v1/depts/{dept_id}", headers=auth(admin_token), params={"move_users_to": target_dept}
    )
    assert ok.status_code == 200
    assert client.get("/api/v1/users/deptuser", headers=auth(admin_token)).json()["dept_id"] == target_dept

    assert client.delete("/api/v1/users/deptuser", headers=auth(admin_token)).status_code == 200
    assert client.delete(f"/api/v1/depts/{target_dept}", headers=auth(admin_token)).status_code == 200


def test_group_list_detail_and_privilege_matrix(client, admin_token, dev_token):
    listed = client.get("/api/v1/groups", headers=auth(admin_token), params={"keyword": "研发"})
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["name"] == "研发-开发"
    assert item["user_count"] == 2
    assert item["priv_count"] == 6

    detail = client.get("/api/v1/groups/1", headers=auth(admin_token))
    assert detail.status_code == 200
    assert {member["account"] for member in detail.json()["members"]} == {"zhangsan", "lisi"}
    assert {p["module"] for p in detail.json()["privileges"]} >= {"user", "dept"}

    matrix = client.get("/api/v1/groups/1/privileges", headers=auth(admin_token))
    assert matrix.status_code == 200
    user_module = next(m for m in matrix.json()["privileges"] if m["module"] == "user")
    checked = {m["method"] for m in user_module["methods"] if m["checked"]}
    assert checked == {"browse"}
    assert len(user_module["methods"]) == 8

    denied = client.get("/api/v1/groups/1/privileges", headers=auth(dev_token))
    assert denied.status_code == 403


def test_group_update_delete_and_members(client, admin_token):
    created = client.post(
        "/api/v1/groups", headers=auth(admin_token), json={"name": "临时-测试组", "desc": "临时"}
    )
    group_id = created.json()["id"]

    duplicated = client.post(
        "/api/v1/groups", headers=auth(admin_token), json={"name": "临时-测试组"}
    )
    assert duplicated.status_code == 409

    bad_priv = client.put(
        f"/api/v1/groups/{group_id}/privileges",
        headers=auth(admin_token),
        json={"privileges": ["user-unknown"]},
    )
    assert bad_priv.status_code == 422

    assert client.put(
        f"/api/v1/groups/{group_id}/privileges",
        headers=auth(admin_token),
        json={"privileges": ["user-browse", "user-browse", "log-view"]},
    ).json()["count"] == 2

    rename = client.patch(
        f"/api/v1/groups/{group_id}", headers=auth(admin_token), json={"name": "临时-质量组", "role": "qa"}
    )
    assert rename.status_code == 200

    members = client.put(
        f"/api/v1/groups/{group_id}/users", headers=auth(admin_token), json={"accounts": ["wangwu"]}
    )
    assert members.status_code == 200
    assert members.json()["count"] == 1

    bad_member = client.put(
        f"/api/v1/groups/{group_id}/users", headers=auth(admin_token), json={"accounts": ["ghost"]}
    )
    assert bad_member.status_code == 422

    blocked = client.delete(f"/api/v1/groups/{group_id}", headers=auth(admin_token))
    assert blocked.status_code == 409

    forced = client.delete(
        f"/api/v1/groups/{group_id}", headers=auth(admin_token), params={"force": True}
    )
    assert forced.status_code == 200
    assert client.get(f"/api/v1/groups/{group_id}", headers=auth(admin_token)).status_code == 404
