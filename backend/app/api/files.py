import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.common.config import settings
from app.common.db import get_db
from app.common.errors import AppError, NotFoundError, ValidationError
from app.files import service
from app.models import FileObject
from app.schemas.requests import FileCompleteIn, FileInitIn

log = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])


@router.post("/uploads")
def init_upload(payload: FileInitIn, db: Session = Depends(get_db)) -> dict:
    """初始化分片上传；同一指纹已存在时直接秒传，未完成会话则续传。"""
    return service.init_upload(
        db, payload.file_name, payload.file_size, payload.file_hash,
        payload.chunk_size or settings.chunk_size, payload.owner_id,
    )


@router.get("/uploads/{upload_id}")
def upload_status(upload_id: str, owner_id: int | None = Query(default=None),
                  db: Session = Depends(get_db)) -> dict:
    """查询已上传/缺失分片，客户端据此跳过已上传部分。"""
    return service.upload_status(db, upload_id, owner_id)


@router.put("/uploads/{upload_id}/chunks/{index}")
async def put_chunk(
    upload_id: str,
    index: int,
    request: Request,
    x_chunk_sha256: str = Header(alias="X-Chunk-SHA256"),
    owner_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """接收单个分片：边读边算 SHA256，校验失败返回 need_retry。"""
    if not x_chunk_sha256:
        raise ValidationError("缺少 X-Chunk-SHA256 请求头")
    return await service.save_chunk(
        db, upload_id, index, request.stream(), x_chunk_sha256, owner_id,
    )


@router.post("/uploads/{upload_id}/complete")
def complete_upload(upload_id: str, payload: FileCompleteIn,
                    db: Session = Depends(get_db)) -> dict:
    """校验所有分片并流式合并；缺片/坏片返回可重传列表。"""
    return service.complete_upload(db, upload_id, payload.file_hash, payload.owner_id)


@router.post("/batch")
async def batch_upload(
    owner_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """小文件批量上传：逐文件流式落盘，允许部分成功。"""
    if len(files) > settings.max_batch_files:
        raise AppError("TOO_MANY_FILES",
                       f"单次最多上传 {settings.max_batch_files} 个文件", 413)

    results: list[dict] = []
    for upload in files:
        name = Path(upload.filename or "").name
        try:
            results.append(await service.save_small_file(db, upload, owner_id))
        except AppError as exc:
            db.rollback()
            results.append({"name": name, "ok": False, "code": exc.code,
                            "error": exc.message})
        except Exception as exc:  # 单个文件失败不影响整批
            log.exception("batch upload failed")
            db.rollback()
            results.append({"name": name, "ok": False, "error": str(exc)})
        finally:
            await upload.close()

    success = sum(1 for item in results if item["ok"])
    return {"total": len(results), "success": success,
            "failed": len(results) - success, "items": results}


@router.get("")
def list_files(owner_id: int = Query(...), db: Session = Depends(get_db)) -> list[dict]:
    return service.list_files(db, owner_id)


@router.get("/{file_id}")
def download(file_id: int, request: Request, db: Session = Depends(get_db)):
    """支持 Range/206 的流式下载；断点续传由客户端保存已下载字节数。"""
    record = db.get(FileObject, file_id)
    if record is None or record.deleted:
        raise NotFoundError("文件不存在")

    path = service.file_path(record.storage_name)
    if not path.exists():
        raise AppError("FILE_GONE", "文件内容已被清理", 410)

    size = path.stat().st_size
    etag = f'"{record.content_hash}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})

    if settings.nginx_accel:
        # 交给 Nginx 用 sendfile 零拷贝发送；Range/206 由 Nginx 原生处理
        return Response(headers={
            "X-Accel-Redirect": f"{settings.nginx_accel_prefix}{record.storage_name}",
            "Content-Type": record.mime or "application/octet-stream",
            "Content-Disposition": service.content_disposition(record.name),
        })

    range_header = request.headers.get("range")
    parsed = service.parse_range(range_header, size)
    if request.headers.get("if-range") and request.headers["if-range"] != etag:
        parsed = None                       # 文件已变化，退回全量
    if parsed == "invalid":
        return Response(status_code=416,
                        headers={"Content-Range": f"bytes */{size}"})

    headers = {
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Content-Disposition": service.content_disposition(record.name),
        "X-File-Hash": record.content_hash,
    }
    media_type = record.mime or "application/octet-stream"

    if parsed is None:
        headers["Content-Length"] = str(size)
        return StreamingResponse(
            service.iter_file(path, 0, size, settings.download_block_size),
            media_type=media_type, headers=headers,
        )

    start, end = parsed
    length = end - start + 1
    headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(length)
    return StreamingResponse(
        service.iter_file(path, start, length, settings.download_block_size),
        status_code=206, media_type=media_type, headers=headers,
    )
