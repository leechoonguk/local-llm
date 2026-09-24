"""seed import food label integration field

Revision ID: 218
Revises: 217

The fourteen columns the service answers, with the whole-feed measurement beside
each (1,087,781 records, 2,176 windows of 500, 2026-09-13).

Widths measured over that walk, which is what the ledger's bounds are cut from:
`KORLABEL` 8,602 · `IRDNT_NM` 2,529 · `OVSMNFST_NM` 307 · `ITM_NM` 221 ·
`PRDUCT_NM` 149 · `PRDUCT_KOREAN_NM` 119 · `BSN_OFC_NAME` 55 · `EXPIRDE_DTM` 19.

The service publishes **no key**. The four fields a record is identified by here
(수입업체 + 제품명(한글) + 처리일자 + 유통기한) leave 1,017,499 distinct of
1,087,781 (93.5%), so the ledger's natural key adds 제품명(영문), 품목, 해외업소
and the two country names - every column the feed answers except the two texts -
and the first live pass measures what that leaves (rule://backend-ledger).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "218"
down_revision: str | Sequence[str] | None = "217"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-import-food-label")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/secret:service-key-import-food")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'serviceKey', 'QUERY', 'SECRET', None, 'STRING', True,
     '인증키 — 수입식품 데이터셋이 승인된 계정의 키 (revision 216)', True, 0),
    ('page_no', 'pageNo', 'QUERY', 'CALLER', None, 'INTEGER', True,
     '페이지 번호 — 1부터', False, 1),
    ('num_of_rows', 'numOfRows', 'QUERY', 'CALLER', None, 'INTEGER', True,
     '한 페이지 결과수 — 500이 상한, 1000·5000은 0건으로 답한다 (2026-09-13 실측)', False, 2),
    ('return_type', 'type', 'QUERY', 'LITERAL', 'json', 'STRING', False,
     '응답데이터 형식 — 이 게이트웨이는 returnType 이 아니라 type 을 읽는다', False, 3),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
ENVELOPE_ROWS = [
    ('result_code', '/header/resultCode', 'ONE_OF', ["00"],
     '결과코드 — 00 정상; 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/header/resultMsg', None, None,
     '결과메시지 — NORMAL SERVICE.', 1),
    ('total_count', '/body/totalCount', None, None,
     '총 결과 건수 — 전량 워크에서 1,087,781 (2026-09-13)', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# **No BODY row is required, and that is the contract, not laziness.** A required
# BODY row vetoes the whole window for one sparse record: measured 2026-09-14 on
# the first live 500-row window, one of the 500 carries an empty 수입업체 and the
# page was refused ("Required response field is missing: importer_name"), where
# the 100-row windows that passed before simply held other rows - this feed's
# order is not stable. The verdict belongs to the ENVELOPE row, which is
# required; a record that cannot be keyed is dropped where it is read
# (`from_record` returns None) and shows up as the gap between received and
# written.
#
# Every pointer is relative to one element of `/body/items`, and an element is
# `{"item": {...}}` — this service wraps each record in its own node.
RESPONSE_ROWS = [
    ('importer_name', '/item/BSN_OFC_NAME', '수입업체명 — 최대 55자; 빈 값인 레코드가 있어 required 가 아니다 (revision 223)', False, 0),
    ('product_name', '/item/PRDUCT_KOREAN_NM', '제품명(한글) — 최대 119자', False, 1),
    ('product_name_en', '/item/PRDUCT_NM', '제품명(영문) — 최대 149자', False, 2),
    ('declaration_kind', '/item/DCL_PRDUCT_SE_CD_NM', '제품구분 — 농.임산물 | 수산물 | 축산물 | 가공식품 | 식품첨가물 | 기구또는용기.포장 | 건강기능식품', False, 3),
    ('product_type_name', '/item/ITM_NM', '품목(유형) — 최대 221자', False, 4),
    ('overseas_maker_name', '/item/OVSMNFST_NM', '해외제조업소 — 최대 307자', False, 5),
    ('origin_country', '/item/MNF_NTNCD_NM', '제조국명', False, 6),
    ('export_country', '/item/XPORT_NTNCD_NM', '수출국명', False, 7),
    ('processed_date', '/item/PROCS_DTM', '처리일자 — YYYYMMDD, 1998-01-30 부터 (연도 분포가 수입식품조회 화면과 일치)', False, 8),
    ('expiry_text', '/item/EXPIRDE_DTM', '유통기한 — "YYYYMMDD ~ YYYYMMDD" 한 문구', False, 9),
    ('expiry_from', '/item/EXPIRDE_BEGIN_DTM', '유통기한 시작일자', False, 10),
    ('expiry_to', '/item/EXPIRDE_END_DTM', '유통기한 종료일자', False, 11),
    ('label_text', '/item/KORLABEL', '한글표시사항 전문 — 1,075,586행(98.9%), 최대 8,602자; 원재료명·함량, 영양정보, 내용량, 포장재질, 알레르기 문구가 이 안에 있다', False, 12),
    ('raw_material_names', '/item/IRDNT_NM', '원재료명 — 7,743행(0.7%)만 채워진다; 원재료는 사실상 label_text 안에 있다', False, 13),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-import-food-label/" + kind)


def _field_table() -> sa.TableClause:
    return table(
        "integration_field",
        column("id", sa.Uuid()),
        column("operation_id", sa.Uuid()),
        column("direction", sa.String()),
        column("location", sa.String()),
        column("key", sa.String()),
        column("wire_path", sa.String()),
        column("locator_kind", sa.String()),
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
            "locator_kind": "POINTER",
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
            "locator_kind": "POINTER",
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
            "locator_kind": "POINTER",
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
