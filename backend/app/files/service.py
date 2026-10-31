"""文件分片上传、合并、批量上传与下载的工具函数。"""

import hashlib
import math
import mimetypes
import os
import shutil
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import quote
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.common.config import settings
from app.common.errors import AppError, ConflictError, NotFoundError, ValidationError
from app.models import FileObject, UploadChunk, UploadSession

CHUNK_MIN = 256 * 1024
CHUNK_MAX = 64 * 1024 * 1024


def sha256_file(path: Path, block: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        while data := fp.read(block):
            digest.update(data)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint(chunk_hashes: list[str]) -> str:
    """文件指纹：按分片顺序拼接各分片 SHA256 后再做一次 SHA256。"""
    return sha256_text("".join(chunk_hashes))


def safe_name(name: str) -> str:
    cleaned = Path(name or "").name.strip()
    if not cleaned:
        raise ValidationError("文件名不能为空")
    return cleaned[:255]


def chunk_size_of(session: UploadSession, index: int) -> int:
    if index < session.total_chunks - 1:
        return session.chunk_size
    return session.file_size - session.chunk_size * (session.total_chunks - 1)


def file_path(storage_name: str) -> Path:
    return settings.file_dir / storage_name


def chunk_path(upload_id: str, index: int) -> Path:
    return settings.chunk_dir / upload_id / f"{index}.part"


def content_disposition(name: str) -> str:
    fallback = name.encode("ascii", "ignore").decode().strip() or "download.bin"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name)}"


def init_upload(db: Session, name: str, size: int, file_hash: str,
                chunk_size: int, owner_id: int) -> dict:
    name = safe_name(name)
    if size <= 0:
        raise ValidationError("空文件不支持分片上传")
    if size > settings.max_upload_size:
        raise AppError("FILE_TOO_LARGE", "文件超过允许的大小", 413)
    if not 32 <= len(file_hash) <= 64:
        raise ValidationError("文件指纹格式不正确")
    chunk_size = max(CHUNK_MIN, min(CHUNK_MAX, chunk_size or settings.chunk_size))

    # 秒传：同一指纹的文件已经存在
    existed = db.scalar(
        select(FileObject).where(FileObject.fingerprint == file_hash,
                                 FileObject.size == size,
                                 FileObject.deleted == 0)
    )
    if existed:
        return {"instant": True, "file_id": existed.id, "file_no": existed.file_no,
                "name": existed.name, "size": existed.size, "file_hash": file_hash}

    # 同一个用户、同一份文件的未完成会话直接复用，实现续传
    session = db.scalar(
        select(UploadSession).where(
            UploadSession.file_hash == file_hash,
            UploadSession.file_size == size,
            UploadSession.owner_id == owner_id,
            UploadSession.status.in_(("uploading", "merging")),
        )
    )
    if session is None:
        total = math.ceil(size / chunk_size)
        session = UploadSession(
            upload_id=uuid4().hex, file_name=name, file_size=size,
            file_hash=file_hash, chunk_size=chunk_size, total_chunks=total,
            status="uploading", owner_id=owner_id,
        )
        db.add(session)
        db.commit()

    uploaded = sorted(c.idx for c in db.scalars(
        select(UploadChunk).where(UploadChunk.upload_id == session.upload_id)))
    return {
        "instant": False,
        "upload_id": session.upload_id,
        "file_hash": session.file_hash,
        "chunk_size": session.chunk_size,
        "total_chunks": session.total_chunks,
        "uploaded": uploaded,
    }


async def save_chunk(db: Session, upload_id: str, index: int,
                     stream: AsyncIterator[bytes], declared_hash: str,
                     owner_id: int | None = None) -> dict:
    session = db.scalar(select(UploadSession).where(UploadSession.upload_id == upload_id))
    if session is None:
        raise NotFoundError("上传会话不存在")
    if owner_id is not None and session.owner_id != owner_id:
        raise AppError("FORBIDDEN", "无权操作该上传会话", 403)
    if session.status != "uploading":
        raise ConflictError("上传会话不在上传状态")
    if not 0 <= index < session.total_chunks:
        raise ValidationError("分片序号越界")

    expected = chunk_size_of(session, index)
    directory = settings.chunk_dir / upload_id
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f"{index}.{uuid4().hex}.tmp"
    final = directory / f"{index}.part"

    digest = hashlib.sha256()
    written = 0
    try:
        with tmp.open("wb") as out:
            async for block in stream:
                written += len(block)
                if written > expected:
                    raise AppError("CHUNK_TOO_LARGE", "分片超出预期大小", 413)
                digest.update(block)
                out.write(block)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    if written != expected:
        tmp.unlink(missing_ok=True)
        raise AppError("CHUNK_SIZE_MISMATCH", "分片大小不符", 422,
                       {"need_retry": [index]})
    actual = digest.hexdigest()
    if actual != declared_hash.lower():
        tmp.unlink(missing_ok=True)
        raise AppError("CHUNK_CHECKSUM_MISMATCH", "分片校验失败", 422,
                       {"need_retry": [index]})

    os.replace(tmp, final)
    db.execute(delete(UploadChunk).where(
        UploadChunk.upload_id == upload_id, UploadChunk.idx == index))
    db.add(UploadChunk(upload_id=upload_id, idx=index, size=written, chunk_hash=actual))
    db.commit()

    count = len(db.scalars(select(UploadChunk.idx).where(
        UploadChunk.upload_id == upload_id)).all())
    return {"index": index, "received": written, "uploaded_count": count}


def upload_status(db: Session, upload_id: str, owner_id: int | None = None) -> dict:
    session = db.scalar(select(UploadSession).where(UploadSession.upload_id == upload_id))
    if session is None:
        raise NotFoundError("上传会话不存在")
    if owner_id is not None and session.owner_id != owner_id:
        raise AppError("FORBIDDEN", "无权查看该上传会话", 403)

    uploaded = sorted(c.idx for c in db.scalars(
        select(UploadChunk).where(UploadChunk.upload_id == upload_id)))
    uploaded_set = set(uploaded)
    missing = [i for i in range(session.total_chunks) if i not in uploaded_set]
    return {
        "upload_id": upload_id,
        "status": session.status,
        "file_name": session.file_name,
        "file_size": session.file_size,
        "chunk_size": session.chunk_size,
        "total_chunks": session.total_chunks,
        "uploaded": uploaded,
        "missing_chunks": missing,
        "file_id": session.file_id,
    }


def complete_upload(db: Session, upload_id: str, file_hash: str | None,
                    owner_id: int | None = None) -> dict:
    session = db.scalar(select(UploadSession).where(UploadSession.upload_id == upload_id))
    if session is None:
        raise NotFoundError("上传会话不存在")
    if owner_id is not None and session.owner_id != owner_id:
        raise AppError("FORBIDDEN", "无权操作该上传会话", 403)
    if session.status == "done" and session.file_id:
        record = db.get(FileObject, session.file_id)
        return {"file_id": session.file_id,
                "file_no": record.file_no if record else None}

    if file_hash and file_hash != session.file_hash:
        raise AppError("FILE_HASH_MISMATCH", "文件指纹与上传会话不一致", 422)

    chunks = sorted(db.scalars(select(UploadChunk).where(
        UploadChunk.upload_id == upload_id)), key=lambda c: c.idx)
    missing = [i for i in range(session.total_chunks)
               if not chunk_path(upload_id, i).exists()]
    if missing:
        raise AppError("CHUNKS_MISSING", "存在未上传的分片", 409,
                       {"missing_chunks": missing})

    # 合并前复核每个分片，防止磁盘损坏
    bad = [c.idx for c in chunks
           if sha256_file(chunk_path(upload_id, c.idx)) != c.chunk_hash]
    if bad:
        for idx in bad:
            chunk_path(upload_id, idx).unlink(missing_ok=True)
            db.execute(delete(UploadChunk).where(
                UploadChunk.upload_id == upload_id, UploadChunk.idx == idx))
        db.commit()
        raise AppError("CHUNK_CORRUPTED", "分片已损坏，请重传", 422,
                       {"need_retry": bad})

    if fingerprint([c.chunk_hash for c in chunks]) != session.file_hash:
        raise AppError("FILE_CHECKSUM_MISMATCH", "整文件校验失败，请重新上传", 422)

    # 只有一个请求能把状态从 uploading 改成 merging
    claimed = db.execute(
        update(UploadSession)
        .where(UploadSession.id == session.id, UploadSession.status == "uploading")
        .values(status="merging")
    ).rowcount
    db.commit()
    if not claimed:
        raise AppError("MERGING", "文件正在合并，请稍后重试", 409)

    try:
        settings.file_dir.mkdir(parents=True, exist_ok=True)
        file_no = uuid4().hex
        storage_name = file_no + Path(session.file_name).suffix[:16]
        tmp = settings.file_dir / f"{storage_name}.tmp"

        digest = hashlib.sha256()
        with tmp.open("wb") as out:
            for c in chunks:
                with chunk_path(upload_id, c.idx).open("rb") as part:
                    while block := part.read(settings.download_block_size):
                        digest.update(block)
                        out.write(block)
        content_hash = digest.hexdigest()
        final = settings.file_dir / storage_name
        os.replace(tmp, final)
    except Exception:
        db.execute(update(UploadSession).where(UploadSession.id == session.id)
                   .values(status="uploading"))
        db.commit()
        raise

    record = FileObject(
        file_no=file_no,
        name=session.file_name,
        storage_name=storage_name,
        size=session.file_size,
        content_hash=content_hash,
        fingerprint=session.file_hash,
        mime=mimetypes.guess_type(session.file_name)[0],
        owner_id=session.owner_id,
    )
    db.add(record)
    db.flush()
    session.status = "done"
    session.file_id = record.id
    session.content_hash = content_hash
    db.commit()
    shutil.rmtree(settings.chunk_dir / upload_id, ignore_errors=True)

    return {"file_id": record.id, "file_no": record.file_no,
            "name": record.name, "size": record.size, "hash": record.content_hash}


async def save_small_file(db: Session, upload: UploadFile, owner_id: int) -> dict:
    name = safe_name(upload.filename or "")
    settings.file_dir.mkdir(parents=True, exist_ok=True)
    file_no = uuid4().hex
    storage_name = file_no + Path(name).suffix[:16]
    dest = settings.file_dir / storage_name

    size = 0
    digest = hashlib.sha256()
    try:
        with dest.open("wb") as out:
            while block := await upload.read(1024 * 1024):
                size += len(block)
                if size > settings.max_batch_file_size:
                    raise AppError("FILE_TOO_LARGE", "单文件超过批量上传限制", 413)
                digest.update(block)
                out.write(block)
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    content_hash = digest.hexdigest()
    record = FileObject(
        file_no=file_no, name=name, storage_name=storage_name, size=size,
        content_hash=content_hash, fingerprint=content_hash,
        mime=upload.content_type or mimetypes.guess_type(name)[0],
        owner_id=owner_id,
    )
    db.add(record)
    db.commit()
    return {"name": name, "ok": True, "file_id": record.id, "size": size}


def list_files(db: Session, owner_id: int) -> list[dict]:
    rows = db.scalars(
        select(FileObject).where(FileObject.owner_id == owner_id, FileObject.deleted == 0)
        .order_by(FileObject.id.desc())
    )
    return [
        {"file_id": f.id, "file_no": f.file_no, "name": f.name, "size": f.size,
         "hash": f.content_hash, "mime": f.mime,
         "url": f"/api/v1/files/{f.id}", "created_at": f.created_at}
        for f in rows
    ]


def delete_file(db: Session, file_id: int, owner_id: int | None = None) -> dict:
    """软删除文件记录，并清理磁盘内容。"""
    record = db.get(FileObject, file_id)
    if record is None or record.deleted:
        raise NotFoundError("文件不存在")
    if owner_id is not None and record.owner_id != owner_id:
        raise AppError("FORBIDDEN", "无权删除该文件", 403)

    record.deleted = 1
    db.commit()
    file_path(record.storage_name).unlink(missing_ok=True)
    return {"file_id": file_id, "deleted": True}


def parse_range(value: str | None, size: int):
    """返回 None、'invalid' 或 (start, end)（闭区间）。"""
    if not value:
        return None
    if not value.startswith("bytes="):
        return "invalid"
    spec = value[6:].split(",")[0].strip()
    left, _, right = spec.partition("-")
    try:
        if left == "":
            start = max(0, size - int(right))
            end = size - 1
        else:
            start = int(left)
            end = int(right) if right else size - 1
    except ValueError:
        return "invalid"
    if start >= size or start > end:
        return "invalid"
    return start, min(end, size - 1)


def iter_file(path: Path, start: int, length: int, block: int):
    with path.open("rb") as fp:
        fp.seek(start)
        while length > 0:
            data = fp.read(min(block, length))
            if not data:
                break
            length -= len(data)
            yield data
