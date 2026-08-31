"""replace mfds integration operation with passthrough response

Revision ID: 51
Revises: 50
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "51"
down_revision: str | Sequence[str] | None = "50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-nutrition/{kind}")


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


def _row(response_mode: str, response_root: str | None) -> dict[str, object]:
    return {
        "id": OPERATION_ID,
        "provider_id": PROVIDER_ID,
        "code": "search-food-nutrition",
        "method": "GET",
        "path_template": "/1471000/FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02",
        "request_media_type": None,
        "response_format": "JSON",
        "response_mode": response_mode,
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


def upgrade() -> None:
    """The provider returns 190+ columns per record, so pass the record through."""
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
    op.bulk_insert(operation, [_row("PASSTHROUGH", "/body/items/0")])


def downgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
    op.bulk_insert(operation, [_row("MAPPED", None)])
