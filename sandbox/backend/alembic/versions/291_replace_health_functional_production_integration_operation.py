"""replace health functional production integration operation with its file door

건강기능식품 생산실적 (I0310) walked whole in about 321 windows, year by year,
and is the one production feed that ever finished - which is why it goes first:
the file door is proved against a ledger whose paged answer is already known.

Measured 2026-09-20 against the file:

    GET /api/{service_key}/I0310/file   200 application/gzip, 5,841,149 bytes,
                                        316,747 records of the same 9 columns
    the paged ledger today              316,746 rows - one row apart, a snapshot
                                        taken minutes later
    every column                        100 % filled but H_ITEM_NM (99.8 %);
                                        EVL_YR holds 2016-2025, ten years in one
                                        answer

`segment_key` and `segment_values` go to NULL. The year coordinate is how a
paged walk reaches ten years one at a time; a file answers all ten at once, and
leaving the coordinate would download the whole file ten times - ten of the ten
downloads a key gets in a day.

Replacing this row cascades `integration_field` away (FK ON DELETE CASCADE),
so revision 292 re-seeds the fields for the file.

Revision ID: 291
Revises: 290
Create Date: 2026-09-20 23:20:47.603443

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "291"
down_revision: str | Sequence[str] | None = "290"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-health-functional-production"
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
        "code": "search-health-functional-production",
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
    """Drop the row; revision 290's tree re-seeds the paged one."""
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
