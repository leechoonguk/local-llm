# ============================================================
# Imports
# ============================================================

from collections.abc import Container
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.scheduler import BATCH_JOBS, validated_cron
from app.models.batch.schedule import BatchSchedule


# ============================================================
# Constants
# ============================================================

NAME_MIN_LENGTH = 1

CODE_MAX_LENGTH = 64

CRON_MAX_LENGTH = 120


# ============================================================
# Classes
# ============================================================


class BatchBase(BaseModel):
    """Field names shared by every direction - deliberately without rules.

    Constraints here would be inherited by `BatchReadResponse`, and a row
    written before a rule existed would then break the list endpoint for every
    caller instead of merely being unwritable. That is not hypothetical for
    `code`: dropping a job from the build must not make the schedules that
    named it unreadable — the operator has to see the row to fix it.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    cron: str
    enabled: bool = True


class BatchCreateRequest(BatchBase):
    """What a client may send. Lengths mirror the columns (`String(64)` /
    `String(120)`), and both `code` and `cron` are checked against the runtime
    that will have to honour them.
    """

    code: str = Field(min_length=NAME_MIN_LENGTH, max_length=CODE_MAX_LENGTH)
    cron: str = Field(min_length=NAME_MIN_LENGTH, max_length=CRON_MAX_LENGTH)

    @field_validator("code")
    @classmethod
    def _check_code(cls, value: str) -> str:
        """Refuse a schedule for a job this build cannot run.

        Raised here rather than in the scheduler module because a Pydantic
        validator is the one place a `ValueError` becomes a 422 instead of a
        500 — every other layer raises a core exception.
        """
        if value not in BATCH_JOBS:
            known = ", ".join(sorted(BATCH_JOBS))
            raise ValueError(f"Unknown batch job code — known codes: {known}")
        return value

    @field_validator("cron")
    @classmethod
    def _check_cron(cls, value: str) -> str:
        return validated_cron(value)


class BatchCreateInternal(BatchBase):
    created_by: str


class BatchReadResponse(BatchBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    #: Whether an execution is in flight right now. Not a column: it is the
    #: scheduler's task map, read per response, so a cached page never reports
    #: last minute's run as still going.
    running: bool = False

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class BatchUpdateRequest(BaseModel):
    """Every field optional, except the one that is missing entirely: `code`.

    A schedule's code is its identity — repointing a row at another job would
    silently change what runs tonight under the row the operator recognises.
    Delete the row and write the one you mean.
    """

    model_config = ConfigDict(extra="forbid")

    cron: str | None = Field(default=None, max_length=CRON_MAX_LENGTH)
    enabled: bool | None = None

    @field_validator("cron")
    @classmethod
    def _check_cron(cls, value: str | None) -> str | None:
        return None if value is None else validated_cron(value)


class BatchUpdateInternal(BatchUpdateRequest):
    updated_by: str


class BatchRunRequest(BaseModel):
    """The execution state the caller wants: run it now, or stop the run."""

    model_config = ConfigDict(extra="forbid")

    running: bool


class BatchRunResponse(BaseModel):
    """The answer to "run it now" and "stop the run".

    `running` is the state the request produced, not the state before it, so a
    client that pressed stop on a job which had just finished reads the same
    `false` as one that cancelled a live run — the wanted end state either way.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    code: str
    running: bool


# ============================================================
# Functions
# ============================================================


def to_read(batch: BatchSchedule, running: bool = False) -> BatchReadResponse:
    return BatchReadResponse.model_validate(batch).model_copy(update={"running": running})


def to_read_list(
    batches: list[BatchSchedule], running_ids: Container[UUID] = frozenset()
) -> list[BatchReadResponse]:
    return [to_read(batch, batch.id in running_ids) for batch in batches]
