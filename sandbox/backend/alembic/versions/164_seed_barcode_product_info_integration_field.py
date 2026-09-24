"""seed barcode product info integration field

Revision ID: 164
Revises: 163

Columns as the portal documents them (`openApiInfo.do?…&svc_no=C005`, read
2026-09-12), with the whole-feed measurement beside each one (259,669
records, 261 windows):

    PRDLST_REPORT_NO  품목보고(신고)번호   16 chars at the widest
    PRMS_DT           보고(신고일)          8  (YYYYMMDD)
    END_DT            생산중단일            8
    PRDLST_NM         제품명              102
    POG_DAYCNT        소비기한            155  - free text ("제조일로부터 …")
    PRDLST_DCNM       식품 유형            55
    BSSH_NM           제조사명             42
    INDUTY_NM         업종                 12
    SITE_ADDR         주소                 15  - the 시도/시군구 only
    CLSBIZ_DT         폐업일자              8
    BAR_CD            유통바코드           27  - several codes arrive as
                                              separate rows, not one string

Keys over the whole feed: 229,040 distinct 바코드, 149,006 distinct
품목보고번호, and 246,195 distinct (바코드, 품목보고번호) pairs over
259,669 rows - 13,474 rows repeat a pair the feed already sent, which the
stage folds into one. The pair is the record's identity and neither half is
unique on its own, so **the required row is `BAR_CD`**: it is the column the
feed exists for, and the one a record is never sent without.

`CHNG_DT` is the one filter the service honours, PATH_QUERY as on every
sibling of this portal. Measured: `20260908` → total 7 (a lower bound
reaching back 7 days), `20240101` → ERROR-303, `2026-09-01` → ERROR-302,
today → INFO-700 (오늘 변경분은 19시 이후), and an unknown key is accepted
and ignored (`[안내]`, unfiltered 259,669) - which is why no other filter
gets a row.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "164"
down_revision: str | Sequence[str] | None = "163"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-barcode-product-info"
)
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'C005', 'STRING', True,
     '서비스명 — 바코드연계제품정보', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('changed_from', 'CHNG_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '변경일자(YYYYMMDD) — 하한(이상). 호출일 기준 7일 이내만(더 오래되면 ERROR-303), 8자리가 아니면 ERROR-302, 당일분은 19시 이후 INFO-700 (2026-09-12 실측)', False, 5),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here. INFO-200 is the empty page
# a window past the last record answers with, which the walk reads as the end
# of the feed.
ENVELOPE_ROWS = [
    ('result_code', '/C005/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/C005/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유 (지원하지 않는 필터의 [안내] 도 여기 실린다)', 1),
    ('total_count', '/C005/total_count', None, None,
     '조건에 해당하는 전체 건수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# `barcode_no` is the required one: the column this feed exists for, and
# half of the pair the ledger keys on.
RESPONSE_ROWS = [
    ('barcode_no', '/BAR_CD', '유통바코드 — 제품이 여러 개를 쓰면 바코드마다 한 행으로 온다', True, 0),
    ('item_report_no', '/PRDLST_REPORT_NO', '품목보고(신고)번호 — food_item_report.item_report_no', False, 1),
    ('permit_date', '/PRMS_DT', '보고(신고일)(YYYYMMDD)', False, 2),
    ('production_end_date', '/END_DT', '생산중단일(YYYYMMDD)', False, 3),
    ('product_name', '/PRDLST_NM', '제품명', False, 4),
    ('shelf_life', '/POG_DAYCNT', '소비기한 — 자유 텍스트("제조일로부터 …")', False, 5),
    ('product_type_name', '/PRDLST_DCNM', '식품 유형', False, 6),
    ('business_name', '/BSSH_NM', '제조사명', False, 7),
    ('industry_name', '/INDUTY_NM', '업종', False, 8),
    ('site_address', '/SITE_ADDR', '주소 — 시도/시군구까지만 온다 (실측 최대 15자)', False, 9),
    ('closed_business_date', '/CLSBIZ_DT', '폐업일자(YYYYMMDD)', False, 10),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-barcode-product-info/" + kind,
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
