# ============================================================
# Imports
# ============================================================

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.batch.step import BatchStep


# ============================================================
# Constants
# ============================================================

FIRST_SEQUENCE = 1

ERROR_CODE_MAX_LENGTH = 64

ERROR_DETAIL_MAX_LENGTH = 512

SUCCEEDED = "SUCCEEDED"

FAILED = "FAILED"


# ============================================================
# Classes
# ============================================================


class BatchStepBase(BaseModel):
    """One finished unit of a run.

    Every count is optional because a unit that failed before the provider
    answered has none — and a zero there would read as "the window was empty",
    which is a different fact.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    sequence: int = Field(ge=FIRST_SEQUENCE)
    status: str = Field(max_length=16)
    range_start: int | None = Field(default=None, ge=FIRST_SEQUENCE)
    range_end: int | None = None
    received: int | None = Field(default=None, ge=0)
    written: int | None = Field(default=None, ge=0)
    duration_ms: int = Field(ge=0)
    integration_call_id: UUID | None = None
    error_code: str | None = Field(default=None, max_length=ERROR_CODE_MAX_LENGTH)
    error_detail: str | None = Field(default=None, max_length=ERROR_DETAIL_MAX_LENGTH)


class BatchStepCreateRequest(BatchStepBase):
    """A unit the job has finished, in either outcome."""


class BatchStepCreateInternal(BatchStepBase):
    created_by: str


class BatchStepReadResponse(BatchStepBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class BatchStepUpdateRequest(BaseModel):
    """A step is written once, when the unit ends.

    Nothing here is a normal edit: the fields exist so a correction is
    expressible at all, and every one of them is a fact about a unit that has
    already finished.
    """

    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(default=None, max_length=16)
    received: int | None = Field(default=None, ge=0)
    written: int | None = Field(default=None, ge=0)
    integration_call_id: UUID | None = None
    error_code: str | None = Field(default=None, max_length=ERROR_CODE_MAX_LENGTH)
    error_detail: str | None = Field(default=None, max_length=ERROR_DETAIL_MAX_LENGTH)


class BatchStepUpdateInternal(BatchStepUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(step: BatchStep) -> BatchStepReadResponse:
    return BatchStepReadResponse.model_validate(step)


def to_read_list(steps: list[BatchStep]) -> list[BatchStepReadResponse]:
    return [BatchStepReadResponse.model_validate(i) for i in steps]
