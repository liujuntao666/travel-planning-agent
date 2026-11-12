"""认证与账号相关的请求模型。"""
import re

from pydantic import BaseModel, Field, field_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,32}$"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _check_password(value: str) -> str:
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("密码必须同时包含字母与数字")
    return value


class CaptchaMixin(BaseModel):
    captcha_id: str = Field(min_length=8, max_length=64)
    captcha_code: str = Field(min_length=2, max_length=8)


class RegisterIn(CaptchaMixin):
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=64)
    nickname: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=128, pattern=EMAIL_PATTERN)
    phone: str | None = Field(default=None, max_length=32, pattern=r"^\+?\d{6,20}$")

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return _check_password(value)

    @field_validator("username")
    @classmethod
    def lower_username(cls, value: str) -> str:
        return value.strip()


class PasswordLoginIn(CaptchaMixin):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=64)

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        return value.strip()


class ForgotPasswordIn(CaptchaMixin):
    account: str = Field(min_length=1, max_length=128, description="用户名或邮箱")

    @field_validator("account")
    @classmethod
    def strip_account(cls, value: str) -> str:
        return value.strip()


class ResetPasswordIn(BaseModel):
    reset_token: str = Field(min_length=16, max_length=128)
    new_password: str = Field(min_length=8, max_length=64)

    @field_validator("new_password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return _check_password(value)
