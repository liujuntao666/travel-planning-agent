from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class IdempotencyRecord(Base, AuditMixin):
    """唯一请求标识记录：同一 Idempotency-Key 只执行一次并回放响应。"""

    __tablename__ = "t_idempotency_record"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PROCESSING", server_default="PROCESSING"
    )
    status_code: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
