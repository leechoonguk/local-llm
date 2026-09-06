"""seed food item report raw material integration field

Revision ID: 107
Revises: 106

Documented columns (portal page `svc_no=C002`, 출력항목) crossed against one
measured record (window 1/2, 2026-09-06), column by column:

    LCNS_NO                인허가번호                   "19970401055"
    BSSH_NM                업소명                       "주식회사 금성에프앤비"
    PRDLST_REPORT_NO       품목제조번호                 "1997040105528"
    PRMS_DT                보고일자                     "20020409"
    PRDLST_NM              품목명                       "가시오가피 냉면"
    PRDLST_DCNM            품목유형명                   "숙면"
    RAWMTRL_NM             원재료명                     "밀가루, 정제수, 타피오카전분, …"
    RAWMTRL_ORDNO          원재료표시순서               "7,8,9,10,11,12"
    CHNG_DT                변경일자(YYYYMMDD)           "20230610"
    ETQTY_XPORT_PRDLST_YN  내수/겸용구분(N:내수, O:겸용) "N"

10 documented, 10 measured, none missing, none extra. The 요청인자 table lists
the five positional segments and eight optional filters; the filters are a
query string relocated into a trailing path segment (PATH_QUERY - measured:
/PRDLST_NM=김치 narrows to 25405, ?PRDLST_NM=김치 is ignored). Two filters are
bounds, not values, so their outbound keys say so:

    CHNG_DT=20260905   1139 rows changed on/after that day; past 7 days ERROR-303
    PRMS_DT=20020409   1057429 of 1071963  <- reported on/after, not on
    PRMS_DT=20250101   230644
    PRMS_DT=20260901   1258

`RAWMTRL_NM` is a substring match the portal runs over a million rows:
RAWMTRL_NM=가시오갈피분말 answers 81 rows in 1s, RAWMTRL_NM=정제수 (an ingredient
of most products) runs 62s and answers ERROR-503 "09시~19시에는 서비스가
제한됩니다" - a server timeout wearing the daytime message, measured at 03:00.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision: str = "107"
down_revision: str | Sequence[str] | None = "106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-item-report-raw-material"
)
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'C002', 'STRING', True,
     '서비스명 — 식품(첨가물)품목제조보고(원재료)', False, 1),
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
    ('product_name', 'PRDLST_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목명 — 추가 파라미터값', False, 7),
    ('business_name', 'BSSH_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '업소명 — 추가 파라미터값', False, 8),
    ('license_no', 'LCNS_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '인허가번호 — 추가 파라미터값', False, 9),
    ('raw_material_name', 'RAWMTRL_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '원재료명 — 부분일치. 흔한 원재료(정제수)는 포털이 60초를 넘겨 ERROR-503으로 거부한다', False, 10),
    ('permit_date_from', 'PRMS_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '보고일자(YYYYMMDD) — 이 날 이후 보고된 자료 (실측: 하한이지 일치가 아니다)', False, 11),
    ('product_type_name', 'PRDLST_DCNM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목유형명 — 추가 파라미터값', False, 12),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here. INFO-200 is an empty page
# (measured one past the total), which a walk reads as the end of the feed.
ENVELOPE_ROWS = [
    ('result_code', '/C002/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/C002/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/C002/total_count', None, None,
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
    ('domestic_export_type', '/ETQTY_XPORT_PRDLST_YN', '내수/겸용구분(N:내수, O:겸용)', False, 9),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"fast-api-standard/mfds-food-safety-korea/search-food-item-report-raw-material/{kind}",
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
