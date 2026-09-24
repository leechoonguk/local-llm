"""seed 식품 생산실적 integration field

Revision ID: 252
Revises: 251

Columns as the portal documents them (`openApiInfo.do?…&svc_no=I0300`, read
2026-09-15) crossed against sampled windows of the live feed (same day):

    PRDLST_REPORT_NO    품목제조보고번호   3,995/4,000 (99.9%), 15 자 - 5 rows carry none
    EVL_YR              보고년도           4,000, 4
    PRDLST_NM           품목명             4,000, 51
    BSSH_NM             업소명             4,000, 36
    LCNS_NO             인허가번호         4,000, 11
    H_ITEM_NM           품목유형           4,000, 13
    PRDCTN_QY           생산량             4,000, 11 - 숫자 문자열
    FYER_PRDCTN_ABRT_QY 연간생산능력       4,000, 11
    SITE_ADDR           주소               4,000, 14

Every documented row arrives; none is missing and none is extra.

`EVL_YR` is seeded as a caller input because this feed is **walked by year**:
the years partition it exactly (연도별 total_count 의 합 = 전체 total_count,
2026-09-15), so walking every year is walking everything, while the offset space
inside one year is a tenth of the whole - and this portal's latency grows with
the offset (14.3 h against 50.2 h over the three 생산실적 services). A caller
input that reads a subset is a filter and is refused (rule://backend-ledger);
one the walk enumerates completely is a coordinate.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "252"
down_revision: str | Sequence[str] | None = "251"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-production")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I0300', 'STRING', True,
     '서비스명 — 식품 생산실적', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('report_year', 'EVL_YR', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '보고년도(YYYY) — 이 피드를 걷는 좌표. 경로 세그먼트로 보내야 거른다 (2026-09-15 실측: 쿼리스트링은 전체 건수를 그대로 돌려준다)', False, 5),
    ('license_no', 'LCNS_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '인허가번호', False, 6),
    ('business_name', 'BSSH_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '업소명', False, 7),
    ('product_type_name', 'PRDLST_CD_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목유형', False, 8),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here, as on every service of this portal.
ENVELOPE_ROWS = [
    ('result_code', '/I0300/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I0300/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/I0300/total_count', None, None,
     '조건에 해당하는 전체 건수 — 연도를 물으면 그 연도의 건수가 온다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('item_report_no', '/PRDLST_REPORT_NO', '품목제조보고번호 — 이 실적이 붙는 제품', True, 0),
    ('report_year', '/EVL_YR', '보고년도(YYYY) — 이 피드를 걷는 좌표이자 키의 한 부분', True, 1),
    ('product_name', '/PRDLST_NM', '품목명 — 같은 번호가 여러 품목명을 갖는다', False, 2),
    ('business_name', '/BSSH_NM', '업소명', False, 3),
    ('license_no', '/LCNS_NO', '인허가번호', False, 4),
    ('product_type_name', '/H_ITEM_NM', '품목유형', False, 5),
    ('production_qty', '/PRDCTN_QY', '생산량(KG, 옹기류는 개) — 숫자 문자열, 소수점 포함', False, 6),
    ('annual_capacity_qty', '/FYER_PRDCTN_ABRT_QY', '연간생산능력(KG, 옹기류는 개)', False, 7),
    ('site_address', '/SITE_ADDR', '주소 — 시·군·구까지', False, 8),
]


def _field_table() -> sa.TableClause:
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
        column("locator_kind", sa.String()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def _field_id(direction: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/search-food-production/field/{direction}/{key}")


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (
        key,
        wire_path,
        location,
        source,
        value,
        value_type,
        required,
        description,
        sensitive,
        ordinal,
    ) in REQUEST_ROWS:
        rows.append(
            {
                "id": _field_id("REQUEST", key),
                "operation_id": OPERATION_ID,
                "direction": "REQUEST",
                "location": location,
                "key": key,
                "wire_path": wire_path,
                "value_source": source,
                "value": value,
                "secret_id": SECRET_ID if source == "SECRET" else None,
                "value_type": value_type,
                "format": None,
                "required": required,
                "description": description,
                "sensitive": sensitive,
                "ordinal": ordinal,
                "enabled": True,
                "match_mode": None,
                "expected_values": None,
                "locator_kind": "POINTER",
                "created_by": "migration",
                "updated_by": "migration",
            }
        )
    for key, wire_path, match_mode, expected, description, ordinal in ENVELOPE_ROWS:
        rows.append(
            {
                "id": _field_id("ENVELOPE", key),
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
                "expected_values": expected,
                "locator_kind": "POINTER",
                "created_by": "migration",
                "updated_by": "migration",
            }
        )
    for key, wire_path, description, required, ordinal in RESPONSE_ROWS:
        rows.append(
            {
                "id": _field_id("RESPONSE", key),
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
                "locator_kind": "POINTER",
                "created_by": "migration",
                "updated_by": "migration",
            }
        )
    return rows


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(_field_table(), _rows())


def downgrade() -> None:
    """Downgrade schema."""
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
