"""seed livestock item report raw material integration field

Revision ID: 116
Revises: 115

Columns measured on one record (window 1/2, 2026-09-07), column by column:

    LCNS_NO                인허가번호                   "19990030770"
    BSSH_NM                업소명                       "노벨유통"
    PRDLST_REPORT_NO       품목제조번호                 "199900307705"
    PRMS_DT                보고일자                     "20040131"
    PRDLST_NM              품목명                       "닭꼬치"
    PRDLST_DCNM            품목유형명                   "포장육"
    RAWMTRL_NM             원재료명                     "닭고기"
    RAWMTRL_ORDNO          원재료표시순서               "1"
    CHNG_DT                변경일자(YYYYMMDD)           "20151102"

9 measured on every record of a 3,988-row sample (4 windows): C002's ten
minus `ETQTY_XPORT_PRDLST_YN` - this feed carries no 내수/겸용 flag. The
filters are the four the portal's own message lists (`사용 가능한 요청인자:
PRDLST_REPORT_NO,CHNG_DT,PRMS_DT,LCNS_NO`, answered to every other key); a
query string is relocated into a trailing path segment as on C002
(PATH_QUERY). Two filters are bounds, not values, so their keys say so:

    CHNG_DT=20260905   51 rows changed on/after that day; past 7 days ERROR-303
    PRMS_DT=20250101   104556 of 569588  <- reported on/after, not on
    PRMS_DT=20260901   670
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision: str = "116"
down_revision: str | Sequence[str] | None = "115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(
    NAMESPACE_URL,
    "fast-api-standard/mfds-food-safety-korea/search-livestock-item-report-raw-material",
)
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'C006', 'STRING', True,
     '서비스명 — 축산물품목제조보고(원재료)', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('change_date', 'CHNG_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '변경일자(YYYYMMDD) — 변경일자 기준 이후 자료를 출력한다 (호출일 기준 7일 이내, 그 밖은 ERROR-303)', False, 5),
    ('item_report_no', 'PRDLST_REPORT_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목제조번호 — 추가 파라미터값', False, 6),
    ('license_no', 'LCNS_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '인허가번호 — 추가 파라미터값', False, 7),
    ('permit_date_from', 'PRMS_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '보고일자(YYYYMMDD) — 이 날 이후 보고된 자료 (실측: 하한이지 일치가 아니다)', False, 8),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here. INFO-200 is an empty page
# (measured one past the total), which a walk reads as the end of the feed.
ENVELOPE_ROWS = [
    ('result_code', '/C006/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/C006/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유 (지원하지 않는 필터의 [안내] 도 여기 실린다)', 1),
    ('total_count', '/C006/total_count', None, None,
     '조건에 해당하는 전체 건수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# `item_report_no` is the required one: it is the key the ledger upserts on,
# and the one column every measured record carried.
RESPONSE_ROWS = [
    ('license_no', '/LCNS_NO', '인허가번호', False, 0),
    ('business_name', '/BSSH_NM', '업소명', False, 1),
    ('item_report_no', '/PRDLST_REPORT_NO', '품목제조번호', True, 2),
    ('permit_date', '/PRMS_DT', '보고일자', False, 3),
    ('product_name', '/PRDLST_NM', '품목명', False, 4),
    ('product_type_name', '/PRDLST_DCNM', '품목유형명', False, 5),
    ('raw_material_names', '/RAWMTRL_NM', '원재료명 — 쉼표로 나열', False, 6),
    ('raw_material_ordinals', '/RAWMTRL_ORDNO', '원재료표시순서 — 쉼표로 나열', False, 7),
    ('changed_date', '/CHNG_DT', '변경일자(YYYYMMDD)', False, 8),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-livestock-item-report-raw-material/"
        + kind,
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
