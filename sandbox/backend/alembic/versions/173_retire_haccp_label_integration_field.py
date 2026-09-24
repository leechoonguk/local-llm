"""retire haccp label integration field

Revision ID: 173
Revises: 172

The HACCP 표기정보 feed goes, and this takes its fields; revision 174 takes
the operation row. Why the feed goes, in one line: **the columns it answers
are free text, and 푸드QR answers the same label as columns.**

Measured on the whole feed and on the first live derivation (2026-09-12):

    nutrient_text  14,392 filled - the printed panel as one string. Split, it
                   produced 83,951 rows under 21,327 distinct names, because
                   an entry carries both the amount and the 1일 기준치 비율
                   (`탄수화물4g 1%`) and nothing in the text says which is
                   which.
    allergy_names  28,324 names, of which 8,507 (30.0 %) read `알수없음` or a
                   variant, plus sentences and `함유` suffixes splitting one
                   allergen across four values.
    barcode        14,378 filled, 8,615 of them the literal `알수없음`.

`getFoodQrProdNsd02` answers the same panel with `NIRWMT_NM` / `CTA` /
`IGRD_UCD` / `NTRTN_RT` / `NTRTN_INDCT_CD` in their own columns, and
`getFoodQrAllrgyInfo02` one row per declared allergen - so the label axis is
rebuilt there instead of on a parser.

The fields go first because `integration_field.operation_id` cascades from
the operation row: deleting the row first would erase these silently and
leave the downgrade nothing to restore them under.

The downgrade re-seeds revision 161's rows verbatim, so a database stepped
back below this revision answers exactly as it did before.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "173"
down_revision: str | Sequence[str] | None = "172"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-haccp-label")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/secret:service-key")

# Revision 161's rows, verbatim - what the downgrade puts back.
# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'serviceKey', 'QUERY', 'SECRET', None, 'STRING', True,
     '인증키 — 공공데이터포털에서 발급된 인증키 (이 provider 의 하나뿐인 service-key)', True, 0),
    ('page_no', 'pageNo', 'QUERY', 'CALLER', None, 'INTEGER', True,
     '페이지 번호 — 1부터', False, 1),
    ('num_of_rows', 'numOfRows', 'QUERY', 'CALLER', None, 'INTEGER', True,
     '한 페이지 결과수 — 100이 상한, 넘기면 resultCode 13 (2026-09-12 실측)', False, 2),
    ('return_type', 'returnType', 'QUERY', 'LITERAL', 'json', 'STRING', False,
     '응답데이터 형식 — 생략하면 xml 로 답한다 (2026-09-12 실측)', False, 3),
    ('item_report_no', 'prdlstReportNo', 'QUERY', 'CALLER', None, 'STRING', False,
     '품목보고번호 — 정확 일치 (201904962715 → total 1, 2026-09-12 실측)', False, 4),
    ('product_name', 'prdlstNm', 'QUERY', 'CALLER', None, 'STRING', False,
     '제품명 — 부분 일치 (김부각 → total 5, 2026-09-12 실측)', False, 5),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
ENVELOPE_ROWS = [
    ('result_code', '/header/resultCode', 'ONE_OF', ["OK"],
     '결과코드 — OK 정상 / 13 numOfRows 상한 초과 등 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/header/resultMessage', None, None,
     '결과메시지 — success, 또는 거부 사유 (numOfRows : LIMITED_OF_DATA_EXCEEDS_ERROR)', 1),
    ('total_count', '/body/totalCount', None, None,
     '요청한 조건에 만족하는 총 결과 건수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('item_report_no', '/item/prdlstReportNo', '품목보고번호 — 제품이 보고된 번호, 레코드의 신원', True, 0),
    ('product_kind_division', '/item/productGb', '축산/식품구분 — 식품 | 축산물', False, 1),
    ('product_name', '/item/prdlstNm', '제품명', False, 2),
    ('raw_material_names', '/item/rawmtrl', '원재료 — 표시면의 원재료명, 쉼표로 이어 붙인 한 문자열', False, 3),
    ('allergy_names', '/item/allergy', '알레르기유발물질 — 없으면 "없음"', False, 4),
    ('nutrient_text', '/item/nutrient', '영양성분 — 포장에 인쇄된 영양표시 본문 (분석값 DB 가 아니다)', False, 5),
    ('barcode_numbers', '/item/barcode', '바코드 — 제품이 여러 개를 쓰면 공백으로 이어 붙여 온다', False, 6),
    ('product_type_name', '/item/prdkind', '유형명 — 식품유형', False, 7),
    ('product_type_state', '/item/prdkindstate', '유형의상태 — 포장 형태 등', False, 8),
    ('maker_name', '/item/manufacture', '제조원', False, 9),
    ('seller_name', '/item/seller', '판매원', False, 10),
    ('capacity_text', '/item/capacity', '용량 — 표시면의 내용량 문구', False, 11),
    ('product_image_url', '/item/imgurl1', '제품이미지URL', False, 12),
    ('label_image_url', '/item/imgurl2', '메타이미지URL — 표시면 이미지', False, 13),
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
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))


def downgrade() -> None:
    op.bulk_insert(_field_table(), _rows())
