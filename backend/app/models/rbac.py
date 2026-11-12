from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, PKMixin


class Role(Base, PKMixin, AuditMixin):
    __tablename__ = "t_role"

    role_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    role_name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class Menu(Base, PKMixin, AuditMixin):
    __tablename__ = "t_menu"

    menu_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    menu_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger)
    path: Mapped[str | None] = mapped_column(String(128))
    icon: Mapped[str | None] = mapped_column(String(64))
    sort_no: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class Permission(Base, PKMixin, AuditMixin):
    __tablename__ = "t_permission"

    perm_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    perm_name: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(64))
    method: Mapped[str | None] = mapped_column(String(16))
    api_path: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class RoleMenu(Base, PKMixin):
    __tablename__ = "t_role_menu"
    __table_args__ = (UniqueConstraint("role_id", "menu_id", name="AK_role_menu"),)

    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_role.id"), nullable=False)
    menu_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_menu.id"), nullable=False)


class RolePermission(Base, PKMixin):
    __tablename__ = "t_role_permission"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="AK_role_permission"),)

    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_role.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_permission.id"), nullable=False
    )


class UserRole(Base, PKMixin):
    __tablename__ = "t_user_role"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="AK_user_role"),)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_user.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_role.id"), nullable=False)
