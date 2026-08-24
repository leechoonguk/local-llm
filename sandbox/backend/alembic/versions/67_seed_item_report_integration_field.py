"""seed food safety korea integration field

Revision ID: 67
Revises: 66
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "67"
down_revision: str | Sequence[str] | None = "66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/item-report")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
#
# Everything this provider takes is a path segment. The five required ones are
# positional (`/api/{key}/{service}/{type}/{start}/{end}`); the seven filters are a
# query string relocated into a trailing segment, which is what PATH_QUERY names.
# Measured: sending them as a real query string is accepted and silently unfiltered.
#
# range_start/range_end are the RANGE paging family: CALLER, required, no default. This
# provider has no page number at all — the window is a row interval.
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I1250', 'STRING', True,
     '서비스명 — 식품(첨가물)품목제조보고', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터, 0은 ERROR-331)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('change_date', 'CHNG_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '변경일자(YYYYMMDD) — 변경일자 기준 이후 자료를 출력한다. 정수입력 : 20170101 (2017년 1월 1일)', False, 5),
    ('item_report_no', 'PRDLST_REPORT_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목제조번호 — 추가 파라미터값', False, 6),
    ('business_name', 'BSSH_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '업소명 — 추가 파라미터값', False, 7),
    ('product_name', 'PRDLST_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '제품명 — 추가 파라미터값', False, 8),
    ('license_no', 'LCNS_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '인허가번호 — 추가 파라미터값', False, 9),
    ('permit_date', 'PRMS_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '보고일자 — 추가 파라미터값', False, 10),
    ('product_type_name', 'PRDLST_DCNM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목유형명 — 추가 파라미터값', False, 11),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# The provider answers HTTP 200 for every outcome and states the real one here.
# Measured: an invalid key answers INFO-100 with no rows, exactly like INFO-200
# ("no data"), so without the checked row an expired credential is an empty page.
# The unchecked rows are carried into metadata — total_count is what a paged caller
# needs to know how far the window can go.
ENVELOPE_ROWS = [
    ('result_code', '/I1250/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"], 'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I1250/RESULT/MSG', None, None, '메세지설명 — provider 가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/I1250/total_count', None, None, '조건에 해당하는 전체 건수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# The 18 columns the service documents, one row each, relative to an element of
# /I1250/row. Keys come from the documented 항목 설명, not from the wire name.
# `product_name` is the required one: a row this service calls a product report has a
# product name, and sparse columns arrive as empty strings.
RESPONSE_ROWS = [
    ('license_no', '/LCNS_NO', '인허가번호', False, 0),
    ('business_name', '/BSSH_NM', '업소명', False, 1),
    ('item_report_no', '/PRDLST_REPORT_NO', '품목제조번호', False, 2),
    ('permit_date', '/PRMS_DT', '허가일자', False, 3),
    ('product_name', '/PRDLST_NM', '제품명', True, 4),
    ('product_type_name', '/PRDLST_DCNM', '품목유형명', False, 5),
    ('production_ended', '/PRODUCTION', '생산종료여부', False, 6),
    ('high_calorie_low_nutrition', '/HIENG_LNTRT_DVS_NM', '고열량저영양식품여부', False, 7),
    ('child_favorite_certified_yn', '/CHILD_CRTFC_YN', '어린이기호식품품질인증여부', False, 8),
    ('shelf_life', '/POG_DAYCNT', '소비기한', False, 9),
    ('last_updated_date', '/LAST_UPDT_DTM', '최종수정일자', False, 10),
    ('industry_name', '/INDUTY_CD_NM', '업종', False, 11),
    ('quality_maintenance_days', '/QLITY_MNTNC_TMLMT_DAYCNT', '품질유지기한일수', False, 12),
    ('usage_method', '/USAGE', '용법', False, 13),
    ('purpose', '/PRPOS', '용도', False, 14),
    ('product_form', '/DISPOS', '제품형태', False, 15),
    ('packaging_material', '/FRMLC_MTRQLT', '포장재질', False, 16),
    ('domestic_export_type', '/ETQTY_XPORT_PRDLST_YN', '내수/겸용구분(N:내수, O:겸용)', False, 17),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-safety-korea/{kind}")


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
            "secret_id": _id("secret:service-key") if value_source == "SECRET" else None,
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
