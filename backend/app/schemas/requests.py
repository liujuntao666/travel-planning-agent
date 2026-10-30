from datetime import date

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    open_id: str = Field(min_length=1, max_length=64)
    nickname: str | None = Field(default=None, max_length=64)
    source: str = Field(default="APP", max_length=32)


class ConversationIn(BaseModel):
    user_id: int
    title: str | None = Field(default=None, max_length=128)


class ChatIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    start_date: date | None = None


class ItemUpdateIn(BaseModel):
    start_time: str | None = None
    end_time: str | None = None
    period: str | None = None
    note: str | None = None


class ItemAddIn(BaseModel):
    day_index: int
    item_type: str = "POI"
    ref_id: int | None = None
    ref_name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration_min: int | None = None
    period: str | None = None
    note: str | None = None


class MoveIn(BaseModel):
    direction: str = Field(pattern="^(up|down)$")


class HotelReplaceIn(BaseModel):
    hotel_id: int


class ExportIn(BaseModel):
    format: str = Field(pattern="^(PDF|LONG_IMAGE|WECHAT_ARTICLE)$")


class FileInitIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    file_size: int = Field(gt=0)
    file_hash: str = Field(min_length=32, max_length=64)
    chunk_size: int | None = Field(default=None, ge=1)
    owner_id: int = Field(gt=0)


class FileCompleteIn(BaseModel):
    file_hash: str | None = Field(default=None, min_length=32, max_length=64)
    owner_id: int | None = Field(default=None, gt=0)
