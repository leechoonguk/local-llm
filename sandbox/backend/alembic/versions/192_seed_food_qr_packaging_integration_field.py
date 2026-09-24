"""seed food qr packaging integration field

Revision ID: 192
Revises: 191

Columns as the portal documents them (read 2026-09-13) with the whole-feed
measurement beside each. The Swagger calls the material column `CSTDY_TRMT` -
the same name its 보관방법 sibling uses - and the wire agrees; the seed keeps the
wire's name on the key it maps to (`packaging_text`), because what arrives here
is a material, not a storage instruction.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "192"
down_revision: str | Sequence[str] | None = "191"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-packaging")
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
    ('label_no', '/ELB_MNG_NO', 'E라벨관리번호 — 3,809개, 푸드QR 계열 중 가장 넓다', True, 0),
    ('detail_serial', '/FOOD_IDIF_DTL_SN', '식품표시정보상세일련번호', True, 1),
    ('item_report_serial', '/IMRPT_SN', '품목제조보고일련번호 — 같은 부위가 두 보고로 오므로 키의 셋째 조각', True, 2),
    ('packaging_text', '/CSTDY_TRMT', '표시내용(용기·포장재질) — `(내면) 폴리프로필렌`, 최대 74자', False, 3),
    ('product_name', '/PRDCT_NM', '제품명', False, 4),
    ('barcode_no', '/BRCD_NO', '바코드번호', False, 5),
    ('version_no', '/VER_NO', '버전번호', False, 6),
    ('valid_from', '/VLD_BGNG_YMD', '유효시작일자 — 6,402/6,914 채움', False, 7),
    ('valid_to', '/VLD_END_YMD', '유효종료일자 — 6,402/6,914 채움', False, 8),
    ('source_updated_at', '/LAST_MDFCN_DT', '최종수정일 — 이 서비스만 날짜(YYYY-MM-DD)로 답한다', False, 9),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-packaging/" + kind)


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
