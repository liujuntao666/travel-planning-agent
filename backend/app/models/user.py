from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, PKMixin


class User(Base, PKMixin, AuditMixin):
    __tablename__ = "t_user"

    open_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    nickname: Mapped[str | None] = mapped_column(String(64))
    avatar_url: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    gender: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    source: Mapped[str | None] = mapped_column(String(32), default="APP", server_default="APP")
    status: Mapped[int | None] = mapped_column(Integer, default=1, server_default="1")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class Conversation(Base, PKMixin, AuditMixin):
    __tablename__ = "t_conversation"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_user.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128))
    last_intent: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[int | None] = mapped_column(Integer, default=1, server_default="1")
    current_trip_id: Mapped[int | None] = mapped_column(BigInteger)
    message_count: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime)


class Message(Base, PKMixin, AuditMixin):
    __tablename__ = "t_message"

    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_conversation.id"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(16), default="TEXT", server_default="TEXT")
    intent: Mapped[str | None] = mapped_column(String(32))
    stream_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    token_count: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    latency_ms: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class RequirementSlot(Base, PKMixin, AuditMixin):
    __tablename__ = "t_requirement_slot"

    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_conversation.id"), nullable=False
    )
    trip_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("t_trip.id"))
    slot_key: Mapped[str] = mapped_column(String(32), nullable=False)
    slot_value: Mapped[str | None] = mapped_column(String(255))
    value_type: Mapped[str | None] = mapped_column(String(16), default="TEXT", server_default="TEXT")
    required_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    filled_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    ask_count: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    slot_source: Mapped[str | None] = mapped_column(String(16), default="EXTRACT", server_default="EXTRACT")
