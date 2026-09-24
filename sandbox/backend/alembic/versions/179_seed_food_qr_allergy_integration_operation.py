"""seed food qr allergy integration operation

Revision ID: 179
Revises: 178

푸드QR 알레르기정보 - `1471000/FoodQrInfoService02/getFoodQrAllrgyInfo02`, the
third of the label trio (revisions 175, 177), same host, same key, same window.

What the feed is: the **declared allergens of a label, one row per allergen** -
E라벨관리번호, 알레르기유발물질일련번호 and the 알레르기유발물질 itself, plus the
product's name, barcode and validity dates. The retired HACCP feed answered the
same thing as one comma-joined string in which 30.0 % of the split values read
`알수없음` (revision 171); here a label with no declared allergen simply has no
row.

Measured 2026-09-12 (whole feed, 18 windows):

    numOfRows=500, pageNo=1     00      8,580 total, 500 rows
    pageNo=100 (past the end)   00      items [] with totalCount still 8,580
    whole feed                  8,580 rows over 1,746 E라벨관리번호
    natural key                 ALG_CSG_MTR_SN — 8,580 distinct on its own;
                                seeded with its label so the pair reads as one
    values                      밀, 대두, 우유, 알류, 돼지고기 … and free-hand
                                variants the publisher types (`조개류(굴, 가리비)`,
                                `조개류()`), so normalising belongs downstream
    IMRPT_SN                    8,566/8,580 — 품목제조보고**일련**번호, not the
                                품목보고번호; only the 영양표시 feed carries that
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "179"
down_revision: str | Sequence[str] | None = "178"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-allergy")

# The page, never its first record: every RESPONSE row is relative to one
# element, and an element here is the record itself - this family answers
# `items` as a plain array (measured 2026-09-12), unlike B553748's `item` node.
PAGE_ROOT = "/body/items"
PATH_TEMPLATE = "/1471000/FoodQrInfoService02/getFoodQrAllrgyInfo02"


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
        column("quota_codes", sa.JSON()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def upgrade() -> None:
    operation = _operation_table()
    op.bulk_insert(
        operation,
        [
            {
                "id": OPERATION_ID,
                "provider_id": PROVIDER_ID,
                "code": "search-food-qr-allergy",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                # A 500-row window answered in about a second through the whole
                # measuring walk (2026-09-12); the sibling's 10 s keeps the same
                # order of headroom.
                "read_timeout_ms": 10000,
                "max_retries": 2,
                "retry_base_ms": 200,
                "retry_max_ms": 1000,
                "idempotent": True,
                "request_schema": None,
                "quota_codes": {},
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
