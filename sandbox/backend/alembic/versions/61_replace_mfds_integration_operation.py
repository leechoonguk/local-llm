"""replace mfds integration operation: map every record on the page

Revision ID: 61
Revises: 60
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "61"
down_revision: str | Sequence[str] | None = "60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")

# The page, not one record in it: an absolute pointer (`/body/items/0`) returned the
# first row however large the page was, so the caller's window was unobservable. The
# RESPONSE rows are now resolved against each element of this node, which is what
# lets one row per provider column describe every record — key, type and the
# provider's own description, for all 193 of them.
#
# Replacing this row cascades integration_field away (FK ON DELETE CASCADE), so
# revision 62 re-seeds the fields.
PAGE_ROOT = "/body/items"


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


def _row() -> dict[str, object]:
    return {
        "id": OPERATION_ID,
        "provider_id": PROVIDER_ID,
        "code": "search-food-nutrition",
        "method": "GET",
        "path_template": "/1471000/FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02",
        "request_media_type": None,
        "response_format": "JSON",
        "response_root": PAGE_ROOT,
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


def upgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
    op.bulk_insert(operation, [_row()])


def downgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
