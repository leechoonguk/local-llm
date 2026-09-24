"""seed common standard exclusion integration field

Revision ID: 126
Revises: 125

Columns as the portal documents them (`openApiInfo.do?…&svc_no=I2610`, read
2026-09-07 - the service itself is closed 09:00-19:00 KST, see revision 122).
The documentation lists no sample values for this service; the ones below
are the vocabularies its siblings use for the same columns:

    CMMN_SPEC_CD           공통기준규격코드             (I2590 code, "000005")
    SPEC_NM                기준규격명                   ("2) 이물")
    PRDLST_CD              품목코드                     (food_product_classification, "C0100000000000")
    KOR_NM                 한글명                       (the 품목's name)
    TESTITM_CD             시험항목코드                 (food_test_item, "H30001")
    LAST_UPDT_DTM          최종수정일시                 ("2019-08-17 16:32:52.644448")

6 documented, no serial: the ledger keys on the triple
(CMMN_SPEC_CD, PRDLST_CD, TESTITM_CD), so all three are required here.
Measured 2026-09-07 evening over the whole feed (21 rows, revision 125):
every record carries all 6, the triple never repeats, no part is ever
empty; a real row is 000008 / C0120010000000 메주 / C20004, stamped
`2020-12-04 10:45:52.703674`. The one filter is the documented
`LAST_UPDT_DTM`, PATH_QUERY as on every sibling of this portal; measured
as on I2590 (revision 122): a lower bound reaching back 7 days
(older -> ERROR-303), a non-8-digit value -> ERROR-302.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "126"
down_revision: str | Sequence[str] | None = "125"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-common-standard-exclusion"
)
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I2610', 'STRING', True,
     '서비스명 — 공통기준제외', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('last_updated_from', 'LAST_UPDT_DTM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '최종수정일(YYYYMMDD) — 유일한 필터, 하한(이상). 호출일 기준 7일 이내만(더 오래되면 ERROR-303), 8자리가 아니면 ERROR-302 (2026-09-07 실측)', False, 5),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here. INFO-200 is an empty page
# on every sibling service (measured one past the total on C006), which a walk
# reads as the end of the feed.
ENVELOPE_ROWS = [
    ('result_code', '/I2610/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I2610/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유 (지원하지 않는 필터의 [안내] 도 여기 실린다)', 1),
    ('total_count', '/I2610/total_count', None, None,
     '조건에 해당하는 전체 건수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# The three code columns are required together: the row carries no serial,
# so the ledger's natural key is their triple (revision 125).
RESPONSE_ROWS = [
    ('common_standard_type_code', '/CMMN_SPEC_CD', '공통기준규격코드 — I2590 의 공통기준종류코드', True, 0),
    ('standard_name', '/SPEC_NM', '기준규격명', False, 1),
    ('product_code', '/PRDLST_CD', '품목코드 — food_product_classification.product_code', True, 2),
    ('product_name', '/KOR_NM', '한글명 — 품목명', False, 3),
    ('test_item_code', '/TESTITM_CD', '시험항목코드 — food_test_item.test_item_code', True, 4),
    ('last_updated_at', '/LAST_UPDT_DTM', '최종수정일시', False, 5),
]

def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-common-standard-exclusion/" + kind,
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
