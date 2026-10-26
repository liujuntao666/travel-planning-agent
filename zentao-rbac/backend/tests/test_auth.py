from tests.conftest import auth, login

PWD = "e10adc3949ba59abbe56e057f20f883e"  # 123456
ADMIN_PWD = "7fef6171469e80d32c0559f88b377245"  # admin888


def test_login_success(client):
    data = login(client, "zhangsan", PWD)
    assert data["token"].startswith("TKN")
    assert data["expires_in"] == 7200
    assert data["user"]["account"] == "zhangsan"
    assert data["user"]["dept_name"] == "研发部"
    assert data["user"]["admin"] == "no"
    assert data["user"]["groups"][0]["name"] == "研发-开发"


def test_login_remember_extended_ttl(client):
    response = client.post(
        "/api/v1/auth/login", json={"account": "zhangsan", "password": PWD, "remember": True}
    )
    assert response.status_code == 200
    assert response.json()["expires_in"] == 604800


def test_login_wrong_password_401(client):
    response = client.post(
        "/api/v1/auth/login", json={"account": "zhangsan", "password": "bad"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
    assert response.json()["message"] == "账号或密码错误"


def test_login_unknown_account_401_same_message(client):
    response = client.post(
        "/api/v1/auth/login", json={"account": "nobody", "password": PWD}
    )
    assert response.status_code == 401
    assert response.json()["message"] == "账号或密码错误"


def test_lock_after_five_failures(client):
    account = "sunqi"
    for _ in range(4):
        response = client.post(
            "/api/v1/auth/login", json={"account": account, "password": "bad"}
        )
        assert response.status_code == 401

    response = client.post("/api/v1/auth/login", json={"account": account, "password": "bad"})
    assert response.status_code == 401

    locked = client.post("/api/v1/auth/login", json={"account": account, "password": PWD})
    assert locked.status_code == 403
    assert locked.json()["code"] == "LOCKED"

    token = login(client, "admin", ADMIN_PWD)["token"]
    unlock = client.post(f"/api/v1/users/{account}/unlock", headers=auth(token))
    assert unlock.status_code == 200

    ok = client.post("/api/v1/auth/login", json={"account": account, "password": PWD})
    assert ok.status_code == 200


def test_me_returns_privileges_and_scope(client, dev_token):
    response = client.get("/api/v1/auth/me", headers=auth(dev_token))
    assert response.status_code == 200
    body = response.json()
    assert "user-browse" in body["privileges"]
    assert "group-editpriv" not in body["privileges"]
    assert body["data_scope"]["products"] == [1, 2]
    assert body["data_scope"]["projects"] == [1]


def test_me_without_token_401(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_change_password_and_logout(client):
    token = login(client, "lisi", PWD)["token"]
    new_pwd = "25d55ad283aa400af464c76d713c07ad"  # 12345678

    bad = client.patch(
        "/api/v1/auth/me/password",
        headers=auth(token),
        json={"old_password": "bad", "new_password": new_pwd},
    )
    assert bad.status_code == 401

    ok = client.patch(
        "/api/v1/auth/me/password",
        headers=auth(token),
        json={"old_password": PWD, "new_password": new_pwd},
    )
    assert ok.status_code == 200

    assert client.post("/api/v1/auth/login", json={"account": "lisi", "password": PWD}).status_code == 401
    new_token = login(client, "lisi", new_pwd)["token"]

    logout = client.post("/api/v1/auth/logout", headers=auth(new_token))
    assert logout.status_code == 200

    revoked = client.get("/api/v1/auth/me", headers=auth(new_token))
    assert revoked.status_code == 401

    admin = login(client, "admin", ADMIN_PWD)["token"]
    reset = client.post(
        "/api/v1/users/lisi/reset-password",
        headers=auth(admin),
        json={"new_password": PWD},
    )
    assert reset.status_code == 200


def test_check_privilege_via(client, dev_token, admin_token):
    mine = client.get(
        "/api/v1/privileges/check", headers=auth(dev_token),
        params={"module": "user", "method": "browse"},
    )
    assert mine.json() == {"allowed": True, "via": "GROUP", "reason": None}

    denied = client.get(
        "/api/v1/privileges/check", headers=auth(dev_token),
        params={"module": "user", "method": "delete"},
    )
    assert denied.json()["allowed"] is False
    assert denied.json()["via"] == "NONE"

    admin = client.get(
        "/api/v1/privileges/check", headers=auth(admin_token),
        params={"module": "user", "method": "delete"},
    )
    assert admin.json() == {"allowed": True, "via": "ADMIN", "reason": None}
