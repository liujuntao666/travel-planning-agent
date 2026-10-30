from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, PKMixin


class FileObject(Base, PKMixin, AuditMixin):
    """已归档的文件元数据，磁盘内容放在 settings.file_dir 下。"""

    __tablename__ = "t_file"

    file_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


class UploadSession(Base, PKMixin, AuditMixin):
    """一次分片上传会话；状态持久化以支持断点续传。"""

    __tablename__ = "t_upload_session"

    upload_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 指纹 = SHA256(按序拼接每个分片的 SHA256)，由客户端与服务端用同一算法计算
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="uploading")
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    file_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class UploadChunk(Base, PKMixin):
    """已成功落盘的分片记录，(upload_id, idx) 唯一保证幂等。"""

    __tablename__ = "t_upload_chunk"
    __table_args__ = (UniqueConstraint("upload_id", "idx", name="uk_chunk_upload_idx"),)

    upload_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), default=datetime.now
    )
