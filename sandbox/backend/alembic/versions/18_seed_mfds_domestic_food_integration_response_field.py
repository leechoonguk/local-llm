"""seed 식품안전나라 국내 식품 조회 response fields

Revision ID: 18
Revises: 17
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "18"
down_revision: str | Sequence[str] | None = "17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-domestic-food-products/search")


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-domestic-food-products/{kind}")


def upgrade() -> None:
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
    response_rows = [
        ("/I1250/row/0/PRDLST_REPORT_NO", "report_no", "STRING"),
        ("/I1250/row/0/PRDLST_NM", "food_name", "STRING"),
        ("/I1250/row/0/BSSH_NM", "manufacturer_name", "STRING"),
        ("/I1250/row/0/PRDLST_DCNM", "food_type", "STRING"),
        ("/I1250/row/0/LCNS_NO", "license_no", "STRING"),
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
                "required": result_key != "license_no",
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
    op.get_bind().execute(
        sa.text("DELETE FROM integration_response_field WHERE operation_id = :operation_id"),
        {"operation_id": OPERATION_ID},
    )
