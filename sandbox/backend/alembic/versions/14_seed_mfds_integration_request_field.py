"""seed 식품안전나라 integration request fields

Revision ID: 14
Revises: 13
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "14"
down_revision: str | Sequence[str] | None = "13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-nutrition/{kind}")


def upgrade() -> None:
    request_field = table(
        "integration_request_field",
        column("id", sa.Uuid()),
        column("operation_id", sa.Uuid()),
        column("input_key", sa.String()),
        column("location", sa.String()),
        column("wire_path", sa.String()),
        column("value_source", sa.String()),
        column("source_key", sa.String()),
        column("literal_value", sa.JSON(none_as_null=True)),
        column("secret_ref", sa.String()),
        column("default_value", sa.JSON(none_as_null=True)),
        column("value_type", sa.String()),
        column("format", sa.String()),
        column("required", sa.Boolean()),
        column("sensitive", sa.Boolean()),
        column("ordinal", sa.Integer()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )
    request_rows = [
        ("service_key", "PATH", "service_key", "SECRET_REF", None, None, "mfds-service-key", "STRING", True, True, 0),
        ("start", "PATH", "start", "LITERAL", None, 1, None, "INTEGER", True, False, 1),
        ("end", "PATH", "end", "LITERAL", None, 100, None, "INTEGER", True, False, 2),
        ("food_name", "QUERY", "DESC_KOR", "CALLER", "food_name", None, None, "STRING", True, False, 3),
    ]
    op.bulk_insert(
        request_field,
        [
            {
                "id": _id(f"request:{input_key}"),
                "operation_id": OPERATION_ID,
                "input_key": input_key,
                "location": location,
                "wire_path": wire_path,
                "value_source": source,
                "source_key": source_key,
                "literal_value": literal_value,
                "secret_ref": secret_ref,
                "default_value": None,
                "value_type": value_type,
                "format": None,
                "required": required,
                "sensitive": sensitive,
                "ordinal": ordinal,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
            for input_key, location, wire_path, source, source_key, literal_value, secret_ref, value_type, required, sensitive, ordinal in request_rows
        ],
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM integration_request_field WHERE operation_id = :operation_id"),
        {"operation_id": OPERATION_ID},
    )
