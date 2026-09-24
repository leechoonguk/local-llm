"""replace food production integration operation with its file door

식품 생산실적 (I0300) is the widest feed of the three and the one the paged
walk had least chance with: the ledger holds 1,034,296 rows of 2025 alone, the
file holds 7,927,213 records over 2016-2025. 7,928 windows do not fit a night
against a daily ceiling of about 500 calls a key - measured in this codebase's
own deck (§13), the offset walk's cost grows with the square of the offset.

Measured 2026-09-20 against the file:

    GET /api/{service_key}/I0300/file   200 application/gzip, 129,778,630 bytes,
                                        7,927,213 records of the same 9 columns
    every column                        100 % filled but PRDLST_REPORT_NO (99.9 %)
    EVL_YR                              2016-2025, ten years in one answer
    업소 55,911 · 소재지 475 · 품목 922, 제품명 174자까지

`segment_key` and `segment_values` go to NULL: the year was how a paged walk
reached one year at a time, and a file answers all ten at once.

Replacing this row cascades `integration_field` away (FK ON DELETE CASCADE),
so revision 296 re-seeds the fields for the file.

Revision ID: 295
Revises: 294
Create Date: 2026-09-20 23:52:00.000000

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "295"
down_revision: str | Sequence[str] | None = "294"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-production"
)

PATH_TEMPLATE = "/api/{service_key}/{service_id}/file"


def _operation_table():
    return table(
        "integration_operation",
        column("id", sa.Uuid()),
        column("provider_id", sa.Uuid()),
        column("code", sa.String()),
        column("method", sa.String()),
        column("path_template", sa.String()),
        column("request_media_type", sa.String()),
        column("response_format", sa.String()),
        column("response_root", sa.String()),
        column("page_size", sa.Integer()),
        column("connect_timeout_ms", sa.Integer()),
        column("read_timeout_ms", sa.Integer()),
        column("max_retries", sa.Integer()),
        column("retry_base_ms", sa.Integer()),
        column("retry_max_ms", sa.Integer()),
        column("idempotent", sa.Boolean()),
        column("request_schema", sa.JSON(none_as_null=True)),
        column("quota_codes", sa.JSON()),
        column("segment_key", sa.String()),
        column("segment_values", sa.JSON(none_as_null=True)),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def _row() -> dict[str, object]:
    return {
        "id": OPERATION_ID,
        "provider_id": PROVIDER_ID,
        "code": "search-food-production",
        "method": "GET",
        "path_template": PATH_TEMPLATE,
        "request_media_type": None,
        "response_format": "CSV",
        "response_root": None,
        # Rows per chunk the stream hands the ledger stage - the same width the
        # paged walk staged, so a step of either walk reads as 1,000 rows.
        "page_size": 1000,
        "connect_timeout_ms": 5000,
        "read_timeout_ms": 60000,
        # A busy key (INFO-500, HTTP 429) clears in about 40 s; the daily ten
        # (INFO-330) it cannot, and three retries do not pretend otherwise.
        "max_retries": 3,
        "retry_base_ms": 15000,
        "retry_max_ms": 60000,
        "idempotent": True,
        "request_schema": None,
        # Nothing arrives in an envelope: a file's refusal is its HTTP status.
        "quota_codes": {},
        "segment_key": None,
        "segment_values": None,
        "enabled": True,
        "created_by": "migration",
        "updated_by": "migration",
    }


def upgrade() -> None:
    """The feed's file door replaces its paged row."""
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
    op.bulk_insert(operation, [_row()])


def downgrade() -> None:
    """Drop the row; the earlier tree re-seeds the paged one."""
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
