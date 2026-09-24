"""seed food qr manufacture integration field

Revision ID: 196
Revises: 195

Columns as the portal documents them (read 2026-09-13) with the whole-feed
measurement beside each. `BSOP_NM` (대표자) is on the wire and not in the
Swagger; the seed follows the wire.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "196"
down_revision: str | Sequence[str] | None = "195"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-manufacture")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'serviceKey', 'QUERY', 'SECRET', None, 'STRING', True,
     '인증키 — 공공데이터포털에서 발급된 인증키 (이 provider 의 하나뿐인 service-key)', True, 0),
    ('page_no', 'pageNo', 'QUERY', 'CALLER', None, 'INTEGER', True,
     '페이지 번호 — 1부터', False, 1),
    ('num_of_rows', 'numOfRows', 'QUERY', 'CALLER', None, 'INTEGER', True,
     '한 페이지 결과수 — 500이 상한, 1000을 보내면 resultCode 11 (2026-09-12 실측)', False, 2),
    ('type', 'type', 'QUERY', 'LITERAL', 'json', 'STRING', False,
     '응답데이터 형식 — 생략하면 xml 로 답한다 (2026-09-12 실측)', False, 3),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# This family answers `00`/`NORMAL SERVICE.` under the 1471000 agency. A window
# past the last page is `00` with an empty `items` list, which the walk reads as
# the end of the feed.
ENVELOPE_ROWS = [
    ('result_code', '/header/resultCode', 'ONE_OF', ["00"],
     '결과코드 — 00 정상 / 11 요청 파라미터 오류 등 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/header/resultMsg', None, None,
     '결과메시지 — NORMAL SERVICE., 또는 거부 사유', 1),
    ('total_count', '/body/totalCount', None, None,
     '전체 결과 수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# Every pointer is relative to one element of `/body/items`, and an element is
# the record itself - this family answers `items` as a plain array.
#
# The keys are the ones the wire answers, measured over the whole feed
# (2026-09-13); the portal's Swagger is quoted where the two agree.
RESPONSE_ROWS = [
    ('label_no', '/ELB_MNG_NO', 'E라벨관리번호 — 2,162개', True, 0),
    ('item_report_serial', '/IMRPT_SN', '품목제조보고일련번호 — 라벨과 짝이면 유일하다', True, 1),
    ('item_report_no', '/IMRPT_NO', '품목제조보고번호 — 전 행 채움, food_item_report 로 이어지는 키', False, 2),
    ('business_name', '/BUES_NM', '업소명', False, 3),
    ('representative_name', '/BSOP_NM', '대표자 — 2,972행, Swagger 에 없고 wire 에만 있다', False, 4),
    ('site_address', '/LCTN_ADDR', '소재지주소 — 2,954행, 우리 어느 테이블에도 없는 값', False, 5),
    ('product_name', '/PRDCT_NM', '제품명', False, 6),
    ('barcode_no', '/BRCD_NO', '바코드번호', False, 7),
    ('version_no', '/VER_NO', '버전번호', False, 8),
    ('valid_from', '/VLD_BGNG_YMD', '유효시작일자 — YYYYMMDD', False, 9),
    ('valid_to', '/VLD_END_YMD', '유효종료일자 — YYYYMMDD', False, 10),
    ('source_updated_at', '/LAST_MDFCN_DT', '최종수정일시 — YYYY-MM-DD HH:MM:SS', False, 11),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-manufacture/" + kind)


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
