"""seed sync barcode ledger batch job

Revision ID: 82
Revises: 81

스케줄은 데이터다: `sync_barcode_ledger` 가 파이썬에만 있으면 어느 환경에서도 돌지 않는다.
새벽으로 잡는 이유는 제공자 쪽 사정이다 — 식품안전나라는 09~19시 KST에 모든 서비스가
`ERROR-503` 로 거절될 수 있다. 갱신분만 읽는 증분 동기화이므로 하루 한 번이면 충분하다.

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op


revision: str = "82"
down_revision: str | Sequence[str] | None = "81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-barcode-ledger")
JOB_CODE = "sync_barcode_ledger"
# 02:00, outside the provider's daytime refusal window and after the ledger's
# readers have gone home.
JOB_CRON = "0 2 * * *"


def upgrade() -> None:
    batch = table(
        "batch",
        column("id", sa.Uuid()),
        column("code", sa.String()),
        column("name", sa.String()),
        column("description", sa.String()),
        column("cron", sa.String()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )
    op.bulk_insert(
        batch,
        [
            {
                "id": JOB_ID,
                "code": JOB_CODE,
                "name": "Sync barcode item ledger",
                "description": (
                    "Migrates 식품바코드 품목정보(I2570) records into the barcode ledger, "
                    "incrementally from the ledger's newest source timestamp."
                ),
                "cron": JOB_CRON,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    batch = table("batch", column("id", sa.Uuid()))
    op.get_bind().execute(batch.delete().where(batch.c.id == JOB_ID))
