from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# SQLite 不支持 BIGINT 自增主键，测试环境退化为 INTEGER
PK_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    pass


class PKMixin:
    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=datetime.now,
        onupdate=datetime.now,
    )
    deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
