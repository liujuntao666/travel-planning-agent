from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base


class Dept(Base):
    __tablename__ = "zt_dept"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    path: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    manager: Mapped[str | None] = mapped_column(String(30), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class User(Base):
    __tablename__ = "zt_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    realname: Mapped[str] = mapped_column(String(50), nullable=False)
    password: Mapped[str] = mapped_column(String(64), nullable=False)
    dept_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="dev")
    admin: Mapped[str] = mapped_column(String(3), nullable=False, default="no")
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active", index=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    login_fails: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class Group(Base):
    __tablename__ = "zt_group"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    role: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class GroupMember(Base):
    __tablename__ = "zt_usergroup"
    __table_args__ = (UniqueConstraint("account", "group_id", name="uk_usergroup"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class Privilege(Base):
    __tablename__ = "zt_privilege"
    __table_args__ = (UniqueConstraint("module", "method", name="uk_privilege"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    module_name: Mapped[str] = mapped_column(String(50), nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class GroupPriv(Base):
    __tablename__ = "zt_grouppriv"
    __table_args__ = (UniqueConstraint("group_id", "module", "method", name="uk_grouppriv"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(30), nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)


class Product(Base):
    __tablename__ = "zt_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    acl_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Project(Base):
    __tablename__ = "zt_project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class ProductAcl(Base):
    __tablename__ = "zt_productacl"
    __table_args__ = (UniqueConstraint("account", "product_id", name="uk_productacl"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)


class ProjectAcl(Base):
    __tablename__ = "zt_projectacl"
    __table_args__ = (UniqueConstraint("account", "project_id", name="uk_projectacl"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)


class OperationLog(Base):
    __tablename__ = "zt_operationlog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    realname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    module: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    result: Mapped[str] = mapped_column(String(10), nullable=False, default="SUCCESS", index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, index=True)


class AuthToken(Base):
    __tablename__ = "zt_auth_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    account: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
