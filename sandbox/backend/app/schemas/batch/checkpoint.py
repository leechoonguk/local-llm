# ============================================================
# Imports
# ============================================================

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.batch.checkpoint import BatchCheckpoint


# ============================================================
# Constants
# ============================================================

SOURCE_CODE_MAX_LENGTH = 64

# The provider's RANGE family is 1-based: row 0 does not exist.
FIRST_RANGE_START = 1

LAST_ROW_KEY_MAX_LENGTH = 200


# ============================================================
# Classes
# ============================================================


class BatchCheckpointBase(BaseModel):
    """How far one external source has been read, and how that position is verified."""

    model_config = ConfigDict(extra="forbid")

    source_code: str = Field(max_length=SOURCE_CODE_MAX_LENGTH)
    next_range_start: int | None = Field(default=None, ge=FIRST_RANGE_START)
    last_row_key: str | None = Field(default=None, max_length=LAST_ROW_KEY_MAX_LENGTH)


class BatchCheckpointCreateRequest(BatchCheckpointBase):
    """The first pass of a source nothing has read yet."""


class BatchCheckpointCreateInternal(BatchCheckpointBase):
    created_by: str


class BatchCheckpointReadResponse(BatchCheckpointBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class BatchCheckpointUpdateRequest(BaseModel):
    """BatchCheckpoint, without the key that says whose checkpoint it is.

    `source_code` is the row's identity: repointing it would hand one source's
    offset to another and skip everything between them.
    """

    model_config = ConfigDict(extra="forbid")

    next_range_start: int | None = Field(default=None, ge=FIRST_RANGE_START)
    last_row_key: str | None = Field(default=None, max_length=LAST_ROW_KEY_MAX_LENGTH)


class BatchCheckpointUpdateInternal(BatchCheckpointUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(checkpoint: BatchCheckpoint) -> BatchCheckpointReadResponse:
    return BatchCheckpointReadResponse.model_validate(checkpoint)


def to_read_list(checkpoints: list[BatchCheckpoint]) -> list[BatchCheckpointReadResponse]:
    return [BatchCheckpointReadResponse.model_validate(i) for i in checkpoints]
