import hashlib
import secrets
from datetime import datetime


def md5_hex(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def new_token() -> str:
    return "TKN" + secrets.token_hex(16).upper()


def fmt_dt(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None
