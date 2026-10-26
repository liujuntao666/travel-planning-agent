from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ROLE = Literal["dev", "qa", "pm", "po", "td"]


class LoginRequest(BaseModel):
    account: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1)
    remember: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=32, max_length=64)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=32, max_length=64)


class UserCreateRequest(BaseModel):
    account: str = Field(pattern=r"^[A-Za-z0-9_]{3,30}$")
    realname: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=32, max_length=64)
    dept_id: int
    role: ROLE
    email: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    group_ids: list[int] = Field(default_factory=list)


class UserPatchRequest(BaseModel):
    realname: str | None = Field(default=None, min_length=1, max_length=50)
    dept_id: int | None = None
    role: ROLE | None = None
    email: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    status: Literal["active", "locked"] | None = None
    admin: Literal["yes", "no"] | None = None


class GroupIdsRequest(BaseModel):
    group_ids: list[int]


class DeptCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: int
    manager: str | None = Field(default=None, max_length=30)
    position: int | None = None


class DeptPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    manager: str | None = Field(default=None, max_length=30)
    position: int | None = None


class DeptMoveRequest(BaseModel):
    parent_id: int


class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str | None = Field(default=None, max_length=10)
    desc: str | None = Field(default=None, max_length=255)
    privileges: list[str] = Field(default_factory=list)


class GroupPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = Field(default=None, max_length=10)
    desc: str | None = Field(default=None, max_length=255)


class GroupUsersRequest(BaseModel):
    accounts: list[str]


class GroupPrivRequest(BaseModel):
    privileges: list[str]


class ProductScopeRequest(BaseModel):
    account: str | None = None
    product_ids: list[int]


class ProjectScopeRequest(BaseModel):
    account: str | None = None
    project_ids: list[int]


class LogQuery(BaseModel):
    account: str | None = None
    module: str | None = None
    method: str | None = None
    result: Literal["SUCCESS", "FAIL"] | None = None
    date_from: date | None = None
    date_to: date | None = None
