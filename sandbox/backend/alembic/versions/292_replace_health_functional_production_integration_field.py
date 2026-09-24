"""replace health functional production integration field with the file's

The fields of the file door (revision 291) - what changed from the paged rows
of revision 256, and what did not:

* REQUEST is the key and the service, and nothing else. The file door takes no
  window and no filter: the year that addressed the paged walk is a column of
  the answer here, not a coordinate of the request.
* No ENVELOPE row. A file's success has no wrapper - the body *is* the rows -
  and its refusal is an HTTP status the client keeps in the call log.
* The RESPONSE rows are **the same nine**, and so are their pointers: a
  one-segment pointer (`/PRDLST_NM`) reads the CSV column of that name, which
  is the API's own column name.

Measured over the whole file, 2026-09-20 (316,747 records):

    BSSH_NM             100 %  915 업소
    PRDLST_NM           100 %  64,832 제품명, 110자까지
    GUBUN               100 %  한 값뿐 - 건강기능식품
    H_ITEM_NM          99.8 %  426 품목
    LCNS_NO             100 %  758 인허가번호
    EVL_YR              100 %  2016-2025, 열 해가 한 답에
    PRDLST_REPORT_NO    100 %  68,241 번호
    FYER_PRDCTN_ABRT_QY 100 %  연간생산능력
    PRDCTN_QY           100 %  생산량

Revision ID: 292
Revises: 291
Create Date: 2026-09-20 23:24:00.000000

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "292"
down_revision: str | Sequence[str] | None = "291"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-health-functional-production"
)
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트). 파일 문의 쿼터는 API 와 별개: 인증키·서비스당 1일 10회 (2026-09-19 실측)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I0310', 'STRING', True,
     '서비스명 — 건강기능식품 생산실적. 경로가 /file 로 끝나면 전체 피드가 gzip CSV 로 온다 (5.8MB, 316,747행)', False, 1),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('item_report_no', '/PRDLST_REPORT_NO', '품목제조신고번호 — 100% 채워진다, 68,241개', True, 0),
    ('report_year', '/EVL_YR', '보고년도 — 2016~2025, 파일 한 번에 열 해가 온다', True, 1),
    ('product_name', '/PRDLST_NM', '제품명 — 64,832개, 110자까지', False, 2),
    ('business_name', '/BSSH_NM', '업소명 — 915개 업소', False, 3),
    ('license_no', '/LCNS_NO', '인허가번호 — 758개', False, 4),
    ('product_type_name', '/H_ITEM_NM', '품목명 — 426개, 99.8% 채워진다', False, 5),
    ('production_qty', '/PRDCTN_QY', '생산량(kg) — 0 이 흔하다(그 해 생산 없음)', False, 6),
    ('annual_capacity_qty', '/FYER_PRDCTN_ABRT_QY', '연간생산능력(kg)', False, 7),
    ('product_kind_name', '/GUBUN', '구분 — 이 피드는 한 값뿐: 건강기능식품', False, 8),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-health-functional-production/" + kind,
    )


def _field_table():
    return table(
        "integration_field",
        column("id", sa.Uuid()),
        column("operation_id", sa.Uuid()),
        column("direction", sa.String()),
        column("location", sa.String()),
        column("key", sa.String()),
        column("wire_path", sa.String()),
        column("value_source", sa.String()),
        column("value", sa.JSON(none_as_null=True)),
        column("secret_id", sa.Uuid()),
        column("value_type", sa.String()),
        column("format", sa.String()),
        column("required", sa.Boolean()),
        column("description", sa.String()),
        column("sensitive", sa.Boolean()),
        column("ordinal", sa.Integer()),
        column("enabled", sa.Boolean()),
        column("match_mode", sa.String()),
        column("expected_values", sa.JSON(none_as_null=True)),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "id": _id(f"field:REQUEST:{key}"),
            "operation_id": OPERATION_ID,
            "direction": "REQUEST",
            "location": location,
            "key": key,
            "wire_path": wire_path,
            "value_source": value_source,
            "value": value,
            "secret_id": SECRET_ID if value_source == "SECRET" else None,
            "value_type": value_type,
            "format": None,
            "required": required,
            "description": description,
            "sensitive": sensitive,
            "ordinal": ordinal,
            "enabled": True,
            "match_mode": None,
            "expected_values": None,
            "created_by": "migration",
            "updated_by": "migration",
        }
        for key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal in REQUEST_ROWS
    ]
    rows.extend(
        {
            "id": _id(f"field:RESPONSE:{key}"),
            "operation_id": OPERATION_ID,
            "direction": "RESPONSE",
            "location": "BODY",
            "key": key,
            "wire_path": wire_path,
            "value_source": None,
            "value": None,
            "secret_id": None,
            "value_type": "STRING",
            "format": None,
            "required": required,
            "description": description,
            "sensitive": False,
            "ordinal": ordinal,
            "enabled": True,
            "match_mode": None,
            "expected_values": None,
            "created_by": "migration",
            "updated_by": "migration",
        }
        for key, wire_path, description, required, ordinal in RESPONSE_ROWS
    )
    return rows


def upgrade() -> None:
    """Seed the file door's fields; revision 291 cascaded the paged ones away."""
    op.bulk_insert(_field_table(), _rows())


def downgrade() -> None:
    """Drop this operation's fields."""
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
