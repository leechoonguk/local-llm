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

# Both paging families are 1-based: there is no row 0 and no page 0.
FIRST_POSITION = 1

RESUME_KEY_MAX_LENGTH = 200


# ============================================================
# Classes
# ============================================================


class BatchCheckpointBase(BaseModel):
    """How far one external source has been read, and how that position is verified."""

    model_config = ConfigDict(extra="forbid")

    source_code: str = Field(max_length=SOURCE_CODE_MAX_LENGTH)
    resume_position: int | None = Field(default=None, ge=FIRST_POSITION)
    resume_key: str | None = Field(default=None, max_length=RESUME_KEY_MAX_LENGTH)


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

    resume_position: int | None = Field(default=None, ge=FIRST_POSITION)
    resume_key: str | None = Field(default=None, max_length=RESUME_KEY_MAX_LENGTH)


class BatchCheckpointUpdateInternal(BatchCheckpointUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(checkpoint: BatchCheckpoint) -> BatchCheckpointReadResponse:
    return BatchCheckpointReadResponse.model_validate(checkpoint)


def to_read_list(checkpoints: list[BatchCheckpoint]) -> list[BatchCheckpointReadResponse]:
    return [BatchCheckpointReadResponse.model_validate(i) for i in checkpoints]
