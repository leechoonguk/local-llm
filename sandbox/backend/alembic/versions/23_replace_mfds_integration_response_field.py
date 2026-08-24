"""replace mfds integration response fields for new endpoint

Revision ID: 23
Revises: 22
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "23"
down_revision: str | Sequence[str] | None = "22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-nutrition/{kind}")


def upgrade() -> None:
    response_field_table = table(
        "integration_response_field",
        column("operation_id", sa.Uuid()),
    )
    op.get_bind().execute(
        response_field_table.delete().where(
            response_field_table.c.operation_id == OPERATION_ID
        )
    )
    response_field = table(
        "integration_response_field",
        column("id", sa.Uuid()),
        column("operation_id", sa.Uuid()),
        column("source_pointer", sa.String()),
        column("result_key", sa.String()),
        column("value_type", sa.String()),
        column("required", sa.Boolean()),
        column("default_value", sa.JSON(none_as_null=True)),
        column("ordinal", sa.Integer()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )
    # (source_pointer, result_key, value_type)
    response_rows = [
        ("/body/items/0/FOOD_NM_KR", "food_name", "STRING"),
        ("/body/items/0/AMT_NUM6", "carbohydrate_g", "NUMBER"),
        ("/body/items/0/AMT_NUM3", "protein_g", "NUMBER"),
        ("/body/items/0/AMT_NUM4", "fat_g", "NUMBER"),
        ("/body/items/0/AMT_NUM13", "sodium_mg", "NUMBER"),
    ]
    op.bulk_insert(
        response_field,
        [
            {
                "id": _id(f"response:{result_key}"),
                "operation_id": OPERATION_ID,
                "source_pointer": source_pointer,
                "result_key": result_key,
                "value_type": value_type,
                "required": True,
                "default_value": None,
                "ordinal": ordinal,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
            for ordinal, (source_pointer, result_key, value_type) in enumerate(response_rows)
        ],
    )


def downgrade() -> None:
    response_field_table = table(
        "integration_response_field",
        column("operation_id", sa.Uuid()),
    )
    op.get_bind().execute(
        response_field_table.delete().where(
            response_field_table.c.operation_id == OPERATION_ID
        )
    )
