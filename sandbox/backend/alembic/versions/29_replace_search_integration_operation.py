"""replace mfds integration operation: remove totalCount from response_schema

Revision ID: 29
Revises: 28
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "29"
down_revision: str | Sequence[str] | None = "28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")

# totalCount is unreliable (returns "" on some queries) — removed from required.
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
                        "required": [
                            "FOOD_NM_KR",
                            "AMT_NUM6",
                            "AMT_NUM3",
                            "AMT_NUM4",
                            "AMT_NUM13",
                        ],
                    },
                },
            },
            "required": ["pageNo", "numOfRows", "items"],
        },
    },
    "required": ["header", "body"],
}


def upgrade() -> None:
    operation_table = table(
        "integration_operation",
        column("id", sa.Uuid()),
        column("response_schema", sa.JSON()),
    )
    op.get_bind().execute(
        operation_table.update()
        .where(operation_table.c.id == OPERATION_ID)
        .values(response_schema=RESPONSE_SCHEMA)
    )


def downgrade() -> None:
    operation_table = table(
        "integration_operation",
        column("id", sa.Uuid()),
        column("response_schema", sa.JSON()),
    )
    op.get_bind().execute(
        operation_table.update()
        .where(operation_table.c.id == OPERATION_ID)
        .values(
            response_schema={
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
                                    "required": [
                                        "FOOD_NM_KR",
                                        "AMT_NUM6",
                                        "AMT_NUM3",
                                        "AMT_NUM4",
                                        "AMT_NUM13",
                                    ],
                                },
                            },
                        },
                        "required": ["pageNo", "totalCount", "numOfRows", "items"],
                    },
                },
                "required": ["header", "body"],
            }
        )
    )
