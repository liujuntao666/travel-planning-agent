from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, PKMixin


class ToolCallLog(Base, PKMixin, AuditMixin):
    __tablename__ = "t_tool_call_log"

    call_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    trace_id: Mapped[str | None] = mapped_column(String(64))
    conversation_id: Mapped[int | None] = mapped_column(BigInteger)
    trip_id: Mapped[int | None] = mapped_column(BigInteger)
    tool_type: Mapped[str] = mapped_column(String(24), nullable=False)
    request_params: Mapped[dict | None] = mapped_column(JSON)
    response_summary: Mapped[str | None] = mapped_column(String(512))
    result_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(16), default="SUCCESS", server_default="SUCCESS")
    degrade_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    cost_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_msg: Mapped[str | None] = mapped_column(String(512))
    called_at: Mapped[datetime | None] = mapped_column(DateTime)


class ContentAuditLog(Base, PKMixin, AuditMixin):
    __tablename__ = "t_content_audit_log"

    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    biz_id: Mapped[int | None] = mapped_column(BigInteger)
    conversation_id: Mapped[int | None] = mapped_column(BigInteger)
    content_digest: Mapped[str | None] = mapped_column(String(64))
    audit_result: Mapped[str | None] = mapped_column(String(16), default="PASS", server_default="PASS")
    risk_level: Mapped[str | None] = mapped_column(String(16))
    risk_label: Mapped[str | None] = mapped_column(String(64))
    auditor: Mapped[str | None] = mapped_column(String(32), default="MACHINE", server_default="MACHINE")
    handle_action: Mapped[str | None] = mapped_column(String(64))
    audited_at: Mapped[datetime | None] = mapped_column(DateTime)
