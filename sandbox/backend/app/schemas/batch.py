# ============================================================
# Imports
# ============================================================

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.batch import Batch


# ============================================================
# Classes
# ============================================================

class BatchBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None


class BatchCreateRequest(BatchBase):
    pass


class BatchCreateInternal(BatchBase):
    created_by: str


class BatchReadResponse(BatchBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class BatchUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None


class BatchUpdateInternal(BatchUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================

def to_read(batch: Batch) -> BatchReadResponse:
    return BatchReadResponse.model_validate(batch)


def to_read_list(batches: list[Batch]) -> list[BatchReadResponse]:
    return [BatchReadResponse.model_validate(i) for i in batches]
