"""seed 식품안전나라 integration operation

Revision ID: 13
Revises: 12
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "13"
down_revision: str | Sequence[str] | None = "12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "I2790": {
            "type": "object",
            "properties": {
                "total_count": {"type": "string"},
                "row": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "DESC_KOR": {"type": "string"},
                            "NUTR_CONT1": {"type": "string"},
                            "NUTR_CONT2": {"type": "string"},
                            "NUTR_CONT3": {"type": "string"},
                            "NUTR_CONT5": {"type": "string"},
                        },
                        "required": ["DESC_KOR", "NUTR_CONT1", "NUTR_CONT2", "NUTR_CONT3", "NUTR_CONT5"],
                    },
                },
            },
            "required": ["total_count", "row"],
        }
    },
    "required": ["I2790"],
}


def upgrade() -> None:
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
                "path_template": "/api/{service_key}/I2790/json/{start}/{end}",
                "request_media_type": None,
                "connect_timeout_ms": 1000,
                "read_timeout_ms": 5000,
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
    op.get_bind().execute(
        sa.text("DELETE FROM integration_operation WHERE id = :id"), {"id": OPERATION_ID}
    )
