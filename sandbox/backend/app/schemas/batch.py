# ============================================================
# Imports
# ============================================================

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.batch import Batch


# ============================================================
# Constants
# ============================================================

NAME_MIN_LENGTH = 1

NAME_MAX_LENGTH = 120

DESCRIPTION_MAX_LENGTH = 512


# ============================================================
# Classes
# ============================================================

class BatchBase(BaseModel):
    """Field names shared by every direction - deliberately without rules.

    Constraints here would be inherited by `BatchReadResponse`, and a row
    written before a rule existed would then break the list endpoint for every
    caller instead of merely being unwritable.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None


class BatchCreateRequest(BatchBase):
    """What a client may send. Lengths mirror the columns (`String(120)` /
    `String(512)`).
    """

    name: str = Field(min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)


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

    name: str | None = Field(
        default=None,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
    )
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)


class BatchUpdateInternal(BatchUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================

def to_read(batch: Batch) -> BatchReadResponse:
    return BatchReadResponse.model_validate(batch)


def to_read_list(batches: list[Batch]) -> list[BatchReadResponse]:
    return [BatchReadResponse.model_validate(i) for i in batches]
