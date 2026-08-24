"""replace mfds integration operation for new endpoint

Revision ID: 21
Revises: 20
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "21"
down_revision: str | Sequence[str] | None = "20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
# Same OPERATION_ID as the original seed so the row is replaced in place.
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "header": {
            "type": "object",
            "properties": {
                "resultCode": {"type": "string"},
                "resultMsg": {"type": "string"},
            },
            "required": ["resultCode", "resultMsg"],
        },
        "body": {
            "type": "object",
            "properties": {
                "pageNo": {"type": "integer"},
                "totalCount": {"type": "integer"},
                "numOfRows": {"type": "integer"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "FOOD_NM_KR": {"type": "string"},
                            "AMT_NUM6": {"type": "string"},
                            "AMT_NUM3": {"type": "string"},
                            "AMT_NUM4": {"type": "string"},
                            "AMT_NUM13": {"type": "string"},
                        },
                        "required": ["FOOD_NM_KR", "AMT_NUM6", "AMT_NUM3", "AMT_NUM4", "AMT_NUM13"],
                    },
                },
            },
            "required": ["pageNo", "totalCount", "numOfRows", "items"],
        },
    },
    "required": ["header", "body"],
}


def upgrade() -> None:
    operation_table = table(
        "integration_operation",
        column("id", sa.Uuid()),
    )
    op.get_bind().execute(
        operation_table.delete().where(operation_table.c.id == OPERATION_ID)
    )
    operation = table(
        "integration_operation",
        column("id", sa.Uuid()),
        column("provider_id", sa.Uuid()),
        column("code", sa.String()),
        column("method", sa.String()),
        column("path_template", sa.String()),
        column("request_media_type", sa.String()),
        column("connect_timeout_ms", sa.Integer()),
        column("read_timeout_ms", sa.Integer()),
        column("max_retries", sa.Integer()),
        column("retry_base_ms", sa.Integer()),
        column("retry_max_ms", sa.Integer()),
        column("idempotent", sa.Boolean()),
        column("request_schema", sa.JSON()),
        column("response_schema", sa.JSON()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )
    op.bulk_insert(
        operation,
        [
            {
                "id": OPERATION_ID,
                "provider_id": PROVIDER_ID,
                "code": "search-food-nutrition",
                "method": "GET",
                "path_template": "/1471000/FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02",
                "request_media_type": None,
                "connect_timeout_ms": 5000,
                "read_timeout_ms": 10000,
                "max_retries": 2,
                "retry_base_ms": 200,
                "retry_max_ms": 1000,
                "idempotent": True,
                "request_schema": None,
                "response_schema": RESPONSE_SCHEMA,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    operation_table = table(
        "integration_operation",
        column("id", sa.Uuid()),
    )
    op.get_bind().execute(
        operation_table.delete().where(operation_table.c.id == OPERATION_ID)
    )
