"""seed food qr nutrition integration operation

Revision ID: 177
Revises: 176

푸드QR 영양표시정보 - `1471000/FoodQrInfoService02/getFoodQrProdNsd02`, the
영양표시 sibling of revision 175's 표시사항, same host, same key, same window.

What the feed is: the **printed 영양표시 panel, already split into columns** -
one row per (E라벨관리번호, 영양표시상세일련번호), carrying the 기준량
(`총 내용량당` | `단위 내용량당` | `100g당` | `100mL당`) with its amount and
unit, the 영양성분명, its 함량 and 성분단위, and the 1일 영양성분 기준치 비율 as
its own number. This is the column the retired HACCP feed could not give: there
the same panel arrived as one string and a parser had to guess which number was
the 함량 and which the 비율 (revisions 170, 173).

Measured 2026-09-12 (whole feed, 52 windows):

    numOfRows=500, pageNo=1     00      25,663 total, 500 rows
    numOfRows=1000              11      INVALID_REQUEST_PARAMETER_ERROR
    whole feed                  25,663 rows over 2,725 E라벨관리번호
    natural key                 (ELB_MNG_NO, NTRTN_IDTL_SN) — 25,663 distinct;
                                NTRTN_IDTL_SN alone is only 24,766
    ?brcdNo / ?imrptNo /
    ?prdctNm / ?elbMngNo        00, totalCount 25,663 — accepted and ignored,
                                so no caller row is seeded
    vocabularies                기준량 4, 영양성분구분 4, 서식 9, 단위 9,
                                영양성분명 84 distinct
    IMRPT_NO                    25,663/25,663 filled — this feed is the one that
                                carries 품목보고번호, so it is what joins the
                                label axis to `food_item_report`
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "177"
down_revision: str | Sequence[str] | None = "176"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-nutrition")

# The page, never its first record: every RESPONSE row is relative to one
# element, and an element here is the record itself - this family answers
# `items` as a plain array (measured 2026-09-12), unlike B553748's `item` node.
PAGE_ROOT = "/body/items"
PATH_TEMPLATE = "/1471000/FoodQrInfoService02/getFoodQrProdNsd02"


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
                "code": "search-food-qr-nutrition",
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
