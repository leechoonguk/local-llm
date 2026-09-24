"""seed health functional closure integration field - the columns of the I2822 file

REQUEST is the key and the service, nothing else: the file door takes no
window and no filter. No ENVELOPE row: the body *is* the rows and a refusal is
an HTTP status. Every RESPONSE row is one CSV column under the API's own name,
read through a one-segment pointer (`/LCNS_NO`).

Measured over the whole file, 2026-09-23 (302,685 rows) - fill rate and width
beside each column below. The columns the ledger declines (`UNSTORED_KEYS` in
its schema) are still seeded here: the contract is what the portal answers,
and a column it answers empty is a fact worth a row.

Revision ID: 311
Revises: 310
Create Date: 2026-09-22 22:09:08.387000

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "311"
down_revision: str | Sequence[str] | None = "310"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-health-functional-closure")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트). 파일 문의 쿼터는 API 와 별개: 인증키·서비스당 1일 10회', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I2822', 'STRING', True,
     '서비스명 — 건강기능식품 폐업정보. 경로가 /file 로 끝나면 전체 피드가 gzip CSV 로 온다 (5.7MB, 302,685행, 2026-09-23)', False, 1),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('license_no', '/LCNS_NO', '인허가번호 — 11자리, 행마다 유일 (302,685행 = 302,685 번호, 2026-09-23 파일 실측)', True, 0),
    ('business_name', '/BSSH_NM', '업소명 — 48자까지', False, 1),
    ('president_name', '/PRSDNT_NM', '대표자명 — 파일 전체에서 빈 값 (0%), 개인정보로 비워 나온다', False, 2),
    ('industry_name', '/INDUTY_NM', '업종 — 건강기능식품일반판매업 296,214 · 유통전문판매업 5,978 · 전문제조업 399 · 벤처제조업 94', False, 3),
    ('permit_date', '/PRMS_DT', '허가일자 — YYYYMMDD', False, 4),
    ('closed_date', '/CLSBIZ_DT', '폐업일자 — YYYYMMDD, 100% 채워진다', False, 5),
    ('closure_kind', '/CLSBIZ_DVS_CD_NM', '폐업구분 — 7개 값', False, 6),
    ('district', '/LOCP_ADDR', '소재지 — 시·군·구까지만 (99.5%)', False, 7),
    ('institution_name', '/INSTT_NM', '관할기관명', False, 8),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-health-functional-closure/" + kind)


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
    """Seed the file door's fields."""
    op.bulk_insert(_field_table(), _rows())


def downgrade() -> None:
    """Drop this operation's fields."""
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
