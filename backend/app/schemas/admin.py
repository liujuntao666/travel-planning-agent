"""后台 RBAC 管理请求模型。"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Status = Literal[0, 1]


class RoleCreateIn(BaseModel):
    role_code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Z][A-Z0-9_]{1,31}$")
    role_name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    status: Status = 1


class RoleUpdateIn(BaseModel):
    role_name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    status: Status | None = None


class MenuCreateIn(BaseModel):
    menu_code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]{1,63}$")
    menu_name: str = Field(min_length=1, max_length=64)
    parent_id: int | None = Field(default=None, ge=1)
    path: str | None = Field(default=None, max_length=128)
    icon: str | None = Field(default=None, max_length=64)
    sort_no: int = Field(default=0, ge=0, le=9999)
    status: Status = 1


class MenuUpdateIn(BaseModel):
    menu_name: str | None = Field(default=None, min_length=1, max_length=64)
    parent_id: int | None = Field(default=None, ge=1)
    path: str | None = Field(default=None, max_length=128)
    icon: str | None = Field(default=None, max_length=64)
    sort_no: int | None = Field(default=None, ge=0, le=9999)
    status: Status | None = None


class PermissionCreateIn(BaseModel):
    perm_code: str = Field(
        min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9:_-]{1,63}$"
    )
    perm_name: str = Field(min_length=1, max_length=64)
    resource: str | None = Field(default=None, max_length=64)
    method: str | None = Field(default=None, max_length=16, pattern=r"^[A-Z]{3,8}$")
    api_path: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    status: Status = 1

    @field_validator("method")
    @classmethod
    def upper_method(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class PermissionUpdateIn(BaseModel):
    perm_name: str | None = Field(default=None, min_length=1, max_length=64)
    resource: str | None = Field(default=None, max_length=64)
    method: str | None = Field(default=None, max_length=16, pattern=r"^[A-Z]{3,8}$")
    api_path: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    status: Status | None = None

    @field_validator("method")
    @classmethod
    def upper_method(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class MenuIdsIn(BaseModel):
    menu_ids: list[int] = Field(default_factory=list, max_length=500)


class PermissionIdsIn(BaseModel):
    permission_ids: list[int] = Field(default_factory=list, max_length=500)


class RoleIdsIn(BaseModel):
    role_ids: list[int] = Field(default_factory=list, max_length=100)
