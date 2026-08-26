# ============================================================
# Imports
# ============================================================

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.notice import Notice


# ============================================================
# Classes
# ============================================================

class NoticeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    content: str
    pinned: bool = False
    published_at: str | None = None


class NoticeCreateRequest(NoticeBase):
    pass


class NoticeCreateInternal(NoticeBase):
    created_by: str


class NoticeReadResponse(NoticeBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class NoticeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    content: str | None = None
    pinned: bool | None = None
    published_at: str | None = None


class NoticeUpdateInternal(NoticeUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================

def to_read(notice: Notice) -> NoticeReadResponse:
    return NoticeReadResponse.model_validate(notice)


def to_read_list(notices: list[Notice]) -> list[NoticeReadResponse]:
    return [NoticeReadResponse.model_validate(n) for n in notices]
