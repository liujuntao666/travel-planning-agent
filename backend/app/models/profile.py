from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, PKMixin


class UserEvent(Base, PKMixin, AuditMixin):
    """用户行为事件：只记录动作与对象标识，不保存对话原文。"""

    __tablename__ = "t_user_event"
    __table_args__ = (Index("idx_user_event_user_time", "user_id", "created_at"),)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_user.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[int | None] = mapped_column(BigInteger)


class TagDict(Base, PKMixin, AuditMixin):
    __tablename__ = "t_tag_dict"

    tag_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    tag_name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class UserTag(Base, PKMixin, AuditMixin):
    """用户标签：带来源与置信度，支持按用户整体清除。"""

    __tablename__ = "t_user_tag"
    __table_args__ = (
        UniqueConstraint("user_id", "tag_code", name="AK_t_user_tag_user_code"),
        Index("idx_user_tag_user", "user_id"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_user.id"), nullable=False)
    tag_code: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    confidence: Mapped[float] = mapped_column(
        Numeric(5, 4), nullable=False, default=1, server_default="1"
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="RULE", server_default="RULE"
    )
