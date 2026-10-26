import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

DB_FILE = Path(tempfile.gettempdir()) / "zentao_rbac_test.db"
if DB_FILE.exists():
    DB_FILE.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.as_posix()}"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["SEED_ON_START"] = "true"
os.environ["LOGIN_MAX_FAILS"] = "5"
os.environ["LOGIN_LOCK_MINUTES"] = "10"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, account: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login", json={"account": account, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="session")
def admin_token(client):
    return login(client, "admin", "7fef6171469e80d32c0559f88b377245")["token"]


@pytest.fixture(scope="session")
def dev_token(client):
    return login(client, "zhangsan", "e10adc3949ba59abbe56e057f20f883e")["token"]


def auth(token: str) -> dict:
    return {"X-Auth-Token": token}
