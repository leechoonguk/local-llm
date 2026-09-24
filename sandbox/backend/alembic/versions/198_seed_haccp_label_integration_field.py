"""seed haccp label integration field

Revision ID: 198
Revises: 197

Columns as the portal documents them (the Swagger of
`data.go.kr/data/15033307/openapi.do`), with the whole-feed measurement beside
each (14,664 records, 147 windows of 100, 2026-09-13).

**Three columns the wire answers are deliberately not seeded**: `nutrient`
(12,932 rows of printed 영양표시 as one sentence - revision 170 measured what
splitting it produces: 21,327 distinct nutrient names, amounts and 기준치 비율
indistinguishable), `imgurl1`/`imgurl2` (product and label photographs, 14,664
each - nothing on this screen shows them). A key not seeded is a column the
ledger never holds, which is the decision, not an oversight.

`barcode` is not seeded either: 5,722 of its 14,378 filled values are numeric and
the rest read `알수없음`, where C005 answers 246,195 barcode rows keyed to the
same 품목보고번호 (revision 166).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "198"
down_revision: str | Sequence[str] | None = "197"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-haccp-label")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'serviceKey', 'QUERY', 'SECRET', None, 'STRING', True,
     '인증키 — 공공데이터포털에서 발급된 인증키 (이 provider 의 하나뿐인 service-key)', True, 0),
    ('page_no', 'pageNo', 'QUERY', 'CALLER', None, 'INTEGER', True,
     '페이지 번호 — 1부터', False, 1),
    ('num_of_rows', 'numOfRows', 'QUERY', 'CALLER', None, 'INTEGER', True,
     '한 페이지 결과수 — 100이 상한, 넘기면 resultCode 13 (2026-09-13 실측)', False, 2),
    ('return_type', 'returnType', 'QUERY', 'LITERAL', 'json', 'STRING', False,
     '응답데이터 형식 — 생략하면 xml 로 답한다 (2026-09-13 실측)', False, 3),
    ('item_report_no', 'prdlstReportNo', 'QUERY', 'CALLER', None, 'STRING', False,
     '품목보고번호 — 정확 일치 (201904962715 → total 1, 2026-09-13 실측)', False, 4),
    ('product_name', 'prdlstNm', 'QUERY', 'CALLER', None, 'STRING', False,
     '제품명 — 부분 일치 (김부각 → total 5, 2026-09-13 실측)', False, 5),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# This agency answers `OK`/`success`, not the `00`/`NORMAL SERVICE.` of the
# 1471000 services under the same host. A window past the last page is `OK` with
# an empty `items` list, which the walk reads as the end of the feed.
ENVELOPE_ROWS = [
    ('result_code', '/header/resultCode', 'ONE_OF', ["OK"],
     '결과코드 — OK 정상 / 13 numOfRows 상한 초과 등 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/header/resultMessage', None, None,
     '결과메시지 — success, 또는 거부 사유 (numOfRows : LIMITED_OF_DATA_EXCEEDS_ERROR)', 1),
    ('total_count', '/body/totalCount', None, None,
     '요청한 조건에 만족하는 총 결과 건수', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# Every pointer is relative to one element of `/body/items`, and an element is
# `{"item": {...}}` — this gateway wraps each record in its own node, unlike the
# 1471000 family's plain array.
RESPONSE_ROWS = [
    ('item_report_no', '/item/prdlstReportNo', '품목보고번호 — 레코드의 신원, 14,664개가 서로 다르다', True, 0),
    ('product_kind_division', '/item/productGb', '축산/식품구분 — 식품 | 축산물', False, 1),
    ('product_name', '/item/prdlstNm', '제품명 — 전 행 채움', False, 2),
    ('raw_material_names', '/item/rawmtrl', '원재료 — 쉼표로 이어 붙인 한 문자열, 전 행 채움 (푸드QR 과 달리 HTML 이 아니다)', False, 3),
    ('allergy_names', '/item/allergy', '알레르기유발물질 — 전 행 채움이지만 8,484행이 `알수없음`, 41행이 `없음` (2026-09-13 실측)', False, 4),
    ('product_type_name', '/item/prdkind', '유형명 — 식품유형, 14,663행', False, 5),
    ('product_type_state', '/item/prdkindstate', '유형의상태 — 포장 형태 등', False, 6),
    ('maker_name', '/item/manufacture', '제조원 — 전 행 채움', False, 7),
    ('seller_name', '/item/seller', '판매원 — 14,486행', False, 8),
    ('capacity_text', '/item/capacity', '용량 — 표시면의 내용량 문구, 14,331행', False, 9),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-haccp-label/" + kind)


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
            "id": _id(f"field:ENVELOPE:{key}"),
            "operation_id": OPERATION_ID,
            "direction": "RESPONSE",
            "location": "ENVELOPE",
            "key": key,
            "wire_path": wire_path,
            "value_source": None,
            "value": None,
            "secret_id": None,
            "value_type": "STRING",
            "format": None,
            "required": match_mode is not None,
            "description": description,
            "sensitive": False,
            "ordinal": ordinal,
            "enabled": True,
            "match_mode": match_mode,
            "expected_values": expected_values,
            "created_by": "migration",
            "updated_by": "migration",
        }
        for key, wire_path, match_mode, expected_values, description, ordinal in ENVELOPE_ROWS
    )
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
    op.bulk_insert(_field_table(), _rows())


def downgrade() -> None:
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
