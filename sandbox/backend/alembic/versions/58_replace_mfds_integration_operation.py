"""replace mfds integration operation: whole page, not the first record

Revision ID: 58
Revises: 57
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "58"
down_revision: str | Sequence[str] | None = "57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")

# `/body/items/0` truncated every answer to one record: a caller could ask for a
# page but only ever saw its first row, so numOfRows changed nothing observable.
# `/body/items` returns the page that was asked for.
#
# The required RESPONSE probe keeps its absolute wire path
# (`/body/items/0/FOOD_NM_KR`), so an empty page still fails instead of handing
# back an empty array as if it were data.
#
# Replacing this row cascades `integration_field` away (FK ON DELETE CASCADE), so
# revision 59 re-seeds the fields. The pair is ordered, not merged: the contract
# test replays the newest `_replace_` per table, which requires one table per
# revision file.
PAGE_ROOT = "/body/items"
RECORD_ROOT = "/body/items/0"


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
        column("response_mode", sa.String()),
        column("response_root", sa.String()),
        column("connect_timeout_ms", sa.Integer()),
        column("read_timeout_ms", sa.Integer()),
        column("max_retries", sa.Integer()),
        column("retry_base_ms", sa.Integer()),
        column("retry_max_ms", sa.Integer()),
        column("idempotent", sa.Boolean()),
        column("request_schema", sa.JSON(none_as_null=True)),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def _row(response_root: str) -> dict[str, object]:
    return {
        "id": OPERATION_ID,
        "provider_id": PROVIDER_ID,
        "code": "search-food-nutrition",
        "method": "GET",
        "path_template": "/1471000/FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02",
        "request_media_type": None,
        "response_format": "JSON",
        "response_mode": "PASSTHROUGH",
        "response_root": response_root,
        "connect_timeout_ms": 5000,
        "read_timeout_ms": 10000,
        "max_retries": 2,
        "retry_base_ms": 200,
        "retry_max_ms": 1000,
        "idempotent": True,
        "request_schema": None,
        "enabled": True,
        "created_by": "migration",
        "updated_by": "migration",
    }


def _replace(response_root: str) -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
    op.bulk_insert(operation, [_row(response_root)])


def upgrade() -> None:
    _replace(PAGE_ROOT)


def downgrade() -> None:
    _replace(RECORD_ROOT)
