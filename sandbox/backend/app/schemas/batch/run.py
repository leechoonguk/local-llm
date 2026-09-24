# ============================================================
# Imports
# ============================================================

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.batch.run import BatchRun


# ============================================================
# Constants
# ============================================================

CODE_MAX_LENGTH = 64

ACTOR_MAX_LENGTH = 50

ERROR_CODE_MAX_LENGTH = 64

ERROR_DETAIL_MAX_LENGTH = 512

# The one status code compares against: a run starts here and every other value
# is an ending. The endings are not spelled a second time as a tuple — nothing
# read it, and `BatchRunStatus` below is the vocabulary.
RUNNING = "RUNNING"


# ============================================================
# Classes
# ============================================================


#: `ck_batch_run_status` — a run is RUNNING or it is one of four endings.
# `SKIPPED` is an ending, not a failure: the derive job fires every day and
# stands down on the days a ledger is still being walked, and the run says so
# rather than leaving the reader to infer it from a zero.
BatchRunStatus = Literal["RUNNING", "SUCCEEDED", "FAILED", "STOPPED", "INTERRUPTED", "SKIPPED"]


#: `ck_batch_run_trigger` — the clock started it, or a person did.
BatchTrigger = Literal["CRON", "MANUAL"]


class BatchRunBase(BaseModel):
    """What every direction of a run row shares."""

    model_config = ConfigDict(extra="forbid")

    batch_id: UUID | None = None
    code: str = Field(max_length=CODE_MAX_LENGTH)
    status: BatchRunStatus
    trigger: BatchTrigger
    triggered_by: str = Field(max_length=ACTOR_MAX_LENGTH)
    stopped_by: str | None = Field(default=None, max_length=ACTOR_MAX_LENGTH)
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    result: int | None = None
    error_code: str | None = Field(default=None, max_length=ERROR_CODE_MAX_LENGTH)
    error_detail: str | None = Field(default=None, max_length=ERROR_DETAIL_MAX_LENGTH)


class BatchRunCreateRequest(BatchRunBase):
    """A run at the moment it starts: status RUNNING, no ending yet."""


class BatchRunCreateInternal(BatchRunBase):
    created_by: str


class BatchRunReadResponse(BatchRunBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class BatchRunUpdateRequest(BaseModel):
    """The ending — everything a run learns after it started.

    `code`, `trigger` and `started_at` are absent on purpose: they are what the
    run *was*, and a log that can be repointed answers nothing.
    """

    model_config = ConfigDict(extra="forbid")

    status: BatchRunStatus | None = None
    stopped_by: str | None = Field(default=None, max_length=ACTOR_MAX_LENGTH)
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    result: int | None = None
    error_code: str | None = Field(default=None, max_length=ERROR_CODE_MAX_LENGTH)
    error_detail: str | None = Field(default=None, max_length=ERROR_DETAIL_MAX_LENGTH)


class BatchRunUpdateInternal(BatchRunUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(run: BatchRun) -> BatchRunReadResponse:
    return BatchRunReadResponse.model_validate(run)


def to_read_list(runs: list[BatchRun]) -> list[BatchRunReadResponse]:
    return [BatchRunReadResponse.model_validate(i) for i in runs]
