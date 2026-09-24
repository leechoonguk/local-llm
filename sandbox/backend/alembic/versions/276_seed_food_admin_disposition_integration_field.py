"""seed food admin disposition integration field

Revision ID: 276
Revises: 275

The wire fields of 행정처분결과(식품제조가공업) — service I0480 on 식품안전나라.
Five required path parts, three optional filters that only filter as path
segments, the envelope this portal answers every outcome with, and the 17
response columns of its 출력항목 table.

Measured 2026-09-18 (the seed operation's docstring carries the whole table):
`DSPSDTLS_SEQ` is the natural key (251 of 251 distinct), `PRSDNT_NM` and
`TELNO` are empty on every row so neither is `required`, and a query-string
filter is accepted and ignored (251) where the path segment filters (1).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "276"
down_revision: str | Sequence[str] | None = "275"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-admin-disposition"
)
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I0480', 'STRING', True,
     '서비스명 — 행정처분결과(식품제조가공업)', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터, 0은 ERROR-331)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('license_no', 'LCNS_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '인허가번호 — 경로 세그먼트로 보내야 거른다(2026-09-18 실측: 경로 1건, 쿼리스트링 251건)', False, 5),
    ('decided_on', 'DSPS_DCSNDT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '확정일자(YYYYMMDD) — 완전일치(2026-09-18 실측: 20260918 → 1건)', False, 6),
    ('changed_from', 'CHNG_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '변경일자(YYYYMMDD) — 이후 자료. 며칠보다 오래된 날짜는 ERROR-303, 8자리가 아니면 ERROR-302 (2026-09-18 실측)', False, 7),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here, as on every service of this
# portal — an invalid key answered INFO-100 with HTTP 200 (2026-09-18 실측).
ENVELOPE_ROWS = [
    ('result_code', '/I0480/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I0480/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/I0480/total_count', None, None,
     '조건에 해당하는 전체 건수 — 251(2026-09-18 실측)', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('disposition_seq', '/DSPSDTLS_SEQ', '행정처분전산키 — 자연키, 251건 전부 유일', True, 0),
    ('business_name', '/PRCSCITYPOINT_BSSHNM', '업소명', False, 1),
    ('industry_name', '/INDUTY_CD_NM', '업종 — 식품제조가공업 또는 식품제조가공업(주류)', False, 2),
    ('license_no', '/LCNS_NO', '인허가번호 — 품목보고(food_item_report.license_no)와 잇는 유일한 키', False, 3),
    ('decided_on', '/DSPS_DCSNDT', '처분확정일자(YYYYMMDD)', False, 4),
    ('began_on', '/DSPS_BGNDT', '처분시작일 — 영업정지의 경우', False, 5),
    ('ended_on', '/DSPS_ENDDT', '처분종료일 — 영업정지의 경우', False, 6),
    ('disposition_type', '/DSPS_TYPECD_NM', '처분유형 — 영업허가·등록취소 / 영업소폐쇄 / 품목제조정지 / 영업정지 …', False, 7),
    ('violation_text', '/VILTCN', '위반일자및위반내용 — 623자까지 측정', False, 8),
    ('address', '/ADDR', '주소 — 시·군·구까지만 공개된다', False, 9),
    ('telephone', '/TELNO', '전화번호 — 251건 전부 공백(2026-09-18 실측)', False, 10),
    ('president_name', '/PRSDNT_NM', '대표자명 — 251건 전부 공백(2026-09-18 실측)', False, 11),
    ('disposition_text', '/DSPSCN', '처분내용 — 111자까지 측정', False, 12),
    ('law_text', '/LAWORD_CD_NM', '위반법령 — 137자까지 측정, 여러 조항이 줄바꿈으로 붙는다', False, 13),
    ('public_until', '/PUBLIC_DT', '공개기한 — "2026-10-03 00:00:00.0" 꼴', False, 14),
    ('source_updated_text', '/LAST_UPDT_DTM', '최종수정일 — "2026-09-18 01:40:19.181" 꼴', False, 15),
    ('institution_name', '/DSPS_INSTTCD_NM', '처분기관명', False, 16),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-food-admin-disposition/" + kind,
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
