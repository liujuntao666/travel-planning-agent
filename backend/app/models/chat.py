from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, PKMixin


class ChatThread(Base, PKMixin, AuditMixin):
    __tablename__ = "t_chat_thread"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_user.id"), nullable=False, unique=True
    )
    advisor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("t_user.id"))
    title: Mapped[str | None] = mapped_column(String(128), default="旅行顾问咨询")
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ChatMessage(Base, PKMixin, AuditMixin):
    __tablename__ = "t_chat_message"
    __table_args__ = (UniqueConstraint("thread_id", "seq", name="uq_chat_thread_seq"),)

    thread_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_chat_thread.id"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    sender_id: Mapped[int | None] = mapped_column(BigInteger)
    sender_role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="USER", server_default="USER"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    read_flag: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
