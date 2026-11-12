import re
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$"
Period = Literal["MORNING", "AFTERNOON", "EVENING", "MEAL"]
ItemType = Literal["POI", "RESTAURANT", "HOTEL", "TRANSPORT", "FREE"]
ExportFormat = Literal["PDF", "LONG_IMAGE", "WECHAT_ARTICLE"]


def _parse_time(value: str) -> time:
    return time.fromisoformat(value if len(value) == 8 else f"{value}:00")


def _check_time_range(start: str | None, end: str | None) -> None:
    if start and end and _parse_time(end) <= _parse_time(start):
        raise ValueError("end_time 必须晚于 start_time")


class LoginIn(BaseModel):
    open_id: str = Field(min_length=1, max_length=64)
    nickname: str | None = Field(default=None, max_length=64)
    source: str = Field(default="APP", max_length=32)

    @field_validator("open_id")
    @classmethod
    def strip_open_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("open_id 不能为空")
        return value


class ConversationIn(BaseModel):
    user_id: int = Field(gt=0)
    title: str | None = Field(default=None, max_length=128)


class ChatIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    start_date: date | None = None

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content 不能为空")
        return value


class ItemUpdateIn(BaseModel):
    start_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    end_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    period: Period | None = None
    note: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def check_range(self):
        _check_time_range(self.start_time, self.end_time)
        return self


class ItemAddIn(BaseModel):
    day_index: int = Field(ge=1)
    item_type: ItemType = "POI"
    ref_id: int | None = Field(default=None, ge=1)
    ref_name: str | None = Field(default=None, max_length=128)
    start_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    end_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    duration_min: int | None = Field(default=None, ge=1, le=1440)
    period: Period | None = None
    note: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def check_payload(self):
        _check_time_range(self.start_time, self.end_time)
        if self.ref_id is None and not (self.ref_name or "").strip():
            raise ValueError("ref_id 与 ref_name 至少提供一个")
        return self


class MoveIn(BaseModel):
    direction: Literal["up", "down"]


class HotelReplaceIn(BaseModel):
    hotel_id: int = Field(gt=0)


class ExportIn(BaseModel):
    format: ExportFormat
