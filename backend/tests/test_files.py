import hashlib
import os
from pathlib import Path

from app.common.config import settings

CHUNK = 5 * 1024 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(parts: list[bytes]) -> str:
    return sha256("".join(sha256(p) for p in parts).encode())


def init_upload(client, user_id: int, data: bytes, name: str, chunk_size: int = CHUNK):
    return client.post("/api/v1/files/uploads", json={
        "file_name": name, "file_size": len(data),
        "file_hash": fingerprint([data[i:i + chunk_size]
                                  for i in range(0, len(data), chunk_size)]),
        "chunk_size": chunk_size, "owner_id": user_id,
    })


def put_chunk(client, upload_id: str, index: int, part: bytes, user_id: int,
              digest: str | None = None):
    return client.put(
        f"/api/v1/files/uploads/{upload_id}/chunks/{index}?owner_id={user_id}",
        content=part,
        headers={"X-Chunk-SHA256": digest or sha256(part)},
    )


def test_chunk_upload_and_bad_chunk_retry(client, user):
    data = os.urandom(10 * 1024 * 1024)
    parts = [data[:CHUNK], data[CHUNK:]]
    uid = user["id"]

    resp = init_upload(client, uid, data, "big.bin")
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["instant"] is False
    assert payload["total_chunks"] == 2
    upload_id = payload["upload_id"]

    # 故意传错分片哈希：服务端应精确告知需要重传第 0 片
    bad = put_chunk(client, upload_id, 0, parts[0], uid, digest="0" * 64)
    assert bad.status_code == 422
    assert bad.json()["code"] == "CHUNK_CHECKSUM_MISMATCH"
    assert bad.json()["need_retry"] == [0]

    assert put_chunk(client, upload_id, 0, parts[0], uid).status_code == 200
    assert put_chunk(client, upload_id, 1, parts[1], uid).status_code == 200

    status = client.get(f"/api/v1/files/uploads/{upload_id}?owner_id={uid}").json()
    assert status["uploaded"] == [0, 1]
    assert status["missing_chunks"] == []

    done = client.post(f"/api/v1/files/uploads/{upload_id}/complete",
                       json={"file_hash": payload["file_hash"], "owner_id": uid})
    assert done.status_code == 200, done.text
    file_id = done.json()["file_id"]

    # 下载与 Range
    full = client.get(f"/api/v1/files/{file_id}")
    assert full.status_code == 200
    assert full.headers["accept-ranges"] == "bytes"
    assert len(full.content) == len(data)

    part = client.get(f"/api/v1/files/{file_id}", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206
    assert len(part.content) == 100
    assert part.headers["content-range"].startswith("bytes 0-99/")

    rest = client.get(f"/api/v1/files/{file_id}", headers={"Range": "bytes=100-"})
    assert rest.status_code == 206
    assert len(rest.content) == len(data) - 100

    invalid = client.get(f"/api/v1/files/{file_id}",
                         headers={"Range": f"bytes={len(data)}-"})
    assert invalid.status_code == 416
    assert invalid.headers["content-range"] == f"bytes */{len(data)}"


def test_resume_reports_missing_chunks(client, user):
    data = os.urandom(15 * 1024 * 1024)
    parts = [data[i:i + CHUNK] for i in range(0, len(data), CHUNK)]
    uid = user["id"]
    payload = init_upload(client, uid, data, "resume.bin").json()
    upload_id = payload["upload_id"]

    assert put_chunk(client, upload_id, 0, parts[0], uid).status_code == 200
    assert put_chunk(client, upload_id, 2, parts[2], uid).status_code == 200

    status = client.get(f"/api/v1/files/uploads/{upload_id}").json()
    assert status["uploaded"] == [0, 2]
    assert status["missing_chunks"] == [1]

    resp = client.post(f"/api/v1/files/uploads/{upload_id}/complete",
                       json={"owner_id": uid})
    assert resp.status_code == 409
    assert resp.json()["missing_chunks"] == [1]


def test_corrupted_chunk_is_detected_before_merge(client, user):
    data = os.urandom(10 * 1024 * 1024)
    parts = [data[:CHUNK], data[CHUNK:]]
    uid = user["id"]
    payload = init_upload(client, uid, data, "corrupt.bin").json()
    upload_id = payload["upload_id"]

    for index, part in enumerate(parts):
        assert put_chunk(client, upload_id, index, part, uid).status_code == 200

    # 模拟磁盘损坏：合并前复核发现分片内容与记录不一致
    target = Path(settings.chunk_dir) / upload_id / "1.part"
    target.write_bytes(b"broken")

    resp = client.post(f"/api/v1/files/uploads/{upload_id}/complete",
                       json={"owner_id": uid})
    assert resp.status_code == 422
    assert resp.json()["code"] == "CHUNK_CORRUPTED"
    assert resp.json()["need_retry"] == [1]

    # 补传坏片后可以正常完成
    assert put_chunk(client, upload_id, 1, parts[1], uid).status_code == 200
    done = client.post(f"/api/v1/files/uploads/{upload_id}/complete",
                       json={"owner_id": uid})
    assert done.status_code == 200, done.text


def test_instant_upload_by_fingerprint(client, user):
    data = os.urandom(6 * 1024 * 1024)
    parts = [data[i:i + CHUNK] for i in range(0, len(data), CHUNK)]
    uid = user["id"]

    first = init_upload(client, uid, data, "same.bin").json()
    upload_id = first["upload_id"]
    for index, part in enumerate(parts):
        assert put_chunk(client, upload_id, index, part, uid).status_code == 200
    done = client.post(f"/api/v1/files/uploads/{upload_id}/complete",
                       json={"owner_id": uid}).json()

    second = init_upload(client, uid, data, "same-again.bin").json()
    assert second["instant"] is True
    assert second["file_id"] == done["file_id"]


def test_batch_upload_and_list(client, user):
    uid = user["id"]
    resp = client.post(
        "/api/v1/files/batch",
        data={"owner_id": str(uid)},
        files=[("files", ("a.txt", b"hello", "text/plain")),
               ("files", ("b.bin", os.urandom(1024), "application/octet-stream"))],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert body["success"] == 2
    assert all(item["ok"] for item in body["items"])

    listed = client.get(f"/api/v1/files?owner_id={uid}").json()
    names = {item["name"] for item in listed}
    assert {"a.txt", "b.bin"} <= names


def test_delete_file_removes_record_and_disk(client, user):
    uid = user["id"]
    before = {p.name for p in Path(settings.file_dir).glob("*")}

    resp = client.post(
        "/api/v1/files/batch",
        data={"owner_id": str(uid)},
        files=[("files", ("del.txt", b"bye", "text/plain")),
               ("files", ("keep.txt", b"stay", "text/plain"))],
    )
    items = resp.json()["items"]
    del_id = next(item["file_id"] for item in items if item["name"] == "del.txt")
    after_upload = {p.name for p in Path(settings.file_dir).glob("*")}
    assert len(after_upload - before) == 2

    forbidden = client.delete(f"/api/v1/files/{del_id}?owner_id={uid + 1}")
    assert forbidden.status_code == 403

    ok = client.delete(f"/api/v1/files/{del_id}?owner_id={uid}")
    assert ok.status_code == 200
    assert ok.json()["deleted"] is True

    listed = client.get(f"/api/v1/files?owner_id={uid}").json()
    assert "del.txt" not in {item["name"] for item in listed}
    assert "keep.txt" in {item["name"] for item in listed}

    gone = client.get(f"/api/v1/files/{del_id}")
    assert gone.status_code == 404

    again = client.delete(f"/api/v1/files/{del_id}?owner_id={uid}")
    assert again.status_code == 404

    # 磁盘内容同步清理，另一个文件不受影响
    remaining = {p.name for p in Path(settings.file_dir).glob("*")}
    assert len(remaining - before) == 1
