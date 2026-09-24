"""replace food collection inspection integration field with the file's

The fields of the file door (revision 286) - what changed from the paged rows
of revision 280, and what did not:

* REQUEST is the key and the service, and nothing else. The file door takes
  no window (a chunk of `page_size` rows is the walk's page) and no filter -
  measured 2026-09-19, the file is the whole feed whatever follows `/file`.
* No ENVELOPE row. A file's success has no wrapper - the body *is* the rows -
  and its refusal is an HTTP 429 with an XML body the client keeps in the call
  log; the status is the verdict.
* The RESPONSE rows are **the same twelve**, and so are their pointers: a
  one-segment pointer (`/PRDTNM`) reads the CSV column of that name, which is
  the API's own column name. Verified against the recorded API window: every
  column identical, to the microsecond of `LAST_UPDT_DTM`.

Revision ID: 287
Revises: 286
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "287"
down_revision: str | Sequence[str] | None = "286"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-collection-inspection"
)
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트). 파일 문의 쿼터는 API 와 별개: 인증키·서비스당 1일 10회 (2026-09-19 실측)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I0460', 'STRING', True,
     '서비스명 — 수거검사 결과. 경로가 /file 로 끝나면 전체 피드가 gzip CSV 로 온다', False, 1),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('collection_no', '/TKAWYPRNO', '수거증번호 — 유일하지 않다. 전 피드에서 651,739건이 중복(2026-09-18 실측)', False, 0),
    ('product_name', '/PRDTNM', '제품명 — 122자까지 측정, 공백은 231건뿐', False, 1),
    ('business_name', '/BSSH_NM', '업소명 — 농수산물·축산물 수거는 업소가 없어 40.8%가 공백', False, 2),
    ('address', '/SITE_ADDR', '소재지 — 시·군·구까지만 공개, 42.0%가 공백', False, 3),
    ('industry_name', '/PRCSCITYPOINT_INDUTYCD_NM', '업종 — 44.5%가 공백', False, 4),
    ('specimen_type', '/TKAWYSPCI_TYPECD_NM', '검체구분 — 가공식품 713,015 / 농산물 318,957 / 식품접객업 284,977 / 축산물(축산물가공품) 282,788 … 요청 코드에 없는 환경검체 395건도 온다', False, 5),
    ('collected_on', '/TKAWYDTM', '수거일자(YYYYMMDD) — 20000214~20260917, 공백 없음', False, 6),
    ('judgment', '/JDGMNT_CD_NM', '판정결과 — 적합 68.3% / 공백 21.1%(미공표) / 상기와같음 5.4% / 검토중 4.7% / 부적합 0.43%(8,861건)', False, 7),
    ('institution_name', '/EXC_INSTT_NM', '수행기관명 — 36자까지 측정', False, 8),
    ('item_report_no', '/PRDLST_REPORT_NO', '품목제조보고번호 — 19자까지, 32.6%만 채워진다. 품목보고(food_item_report)와 잇는 유일한 키', False, 9),
    ('plan_title', '/PLAN_TITL', '수거계획명 — 어떤 계획으로 수거했는지, 4.9%가 공백', False, 10),
    ('source_updated_text', '/LAST_UPDT_DTM', '최종수정일시 — "2026-09-18 16:25:59.676351" 꼴', False, 11),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-food-collection-inspection/" + kind,
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
