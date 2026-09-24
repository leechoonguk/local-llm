"""lay the nightly schedule out by quota and night

The portal is closed 09:00-19:00 KST, so a night is fourteen hours; and it
refuses a key that has spent 500 calls on one service that day, so a service can
be walked 1,500 windows a day with the three keys this deployment holds. Those
two numbers, not preference, decide what may share a night.

What changes:

- The 생산실적 feeds move from weekly to monthly. They are published once a year,
  and they are the only feeds larger than a day's quota: 식품 7,928 windows (six
  days), 축산 3,398 (three), 건기식 321 (one night). A run above the daily ceiling
  does not fail - it sits its keys out and continues after midnight - so a
  monthly slot with days of room is the shape that fits, and the first of the
  month is the room.
- 품목제조보고 and 품목 원재료 move off Saturday's small hours onto Saturday night:
  measured 2h35 and 3h04, which is most of one night between them.
- The data.go.kr feeds move to Sunday night. They are a different provider with a
  different quota, so they never had to share Friday with 식품안전나라.

The small mfds feeds keep their Friday evening slots: together they are under
200 windows and an hour.

Revision ID: 273
Revises: 272
Create Date: 2026-09-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "273"
down_revision: str | Sequence[str] | None = "272"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# code → cron, for every row this revision moves. Day-of-week: 5=Fri, 6=Sat, 0=Sun.
SCHEDULE = {
    # Saturday night: the two million-row 식품안전나라 feeds, back to back.
    "sync_food_ledger_item_report": "0 19 * * 6",
    "sync_food_ledger_item_report_raw_material": "30 22 * * 6",
    "sync_food_ledger_livestock_item_report_raw_material": "0 2 * * 0",
    # Friday night, after the small feeds.
    "sync_food_ledger_barcode": "0 22 * * 5",
    # Sunday night: data.go.kr, a provider of its own with a quota of its own.
    "sync_food_ledger_import_food_label": "0 19 * * 0",
    "sync_food_ledger_nutrition": "30 19 * * 0",
    "sync_food_ledger_haccp_label": "30 20 * * 0",
    "sync_food_ledger_qr_label": "0 21 * * 0",
    "sync_food_ledger_qr_raw_material": "10 21 * * 0",
    "sync_food_ledger_qr_storage": "20 21 * * 0",
    "sync_food_ledger_qr_manufacture": "30 21 * * 0",
    "sync_food_ledger_qr_packaging": "40 21 * * 0",
    "sync_food_ledger_qr_caution": "50 21 * * 0",
    "sync_food_ledger_qr_allergy": "0 22 * * 0",
    "sync_food_ledger_qr_nutrition": "10 22 * * 0",
    # Monthly: the 생산실적 feeds, each with days of room after it.
    "sync_food_ledger_production": "0 19 1 * *",
    "sync_food_ledger_livestock_production": "0 19 10 * *",
    "sync_food_ledger_health_functional_production": "0 19 14 * *",
}

PREVIOUS_SCHEDULE = {
    "sync_food_ledger_item_report": "30 0 * * 6",
    "sync_food_ledger_item_report_raw_material": "30 3 * * 6",
    "sync_food_ledger_livestock_item_report_raw_material": "0 21 * * 5",
    "sync_food_ledger_barcode": "30 20 * * 5",
    "sync_food_ledger_import_food_label": "0 20 * * 5",
    "sync_food_ledger_nutrition": "30 21 * * 5",
    "sync_food_ledger_haccp_label": "15 1 * * 6",
    "sync_food_ledger_qr_label": "10 23 * * 5",
    "sync_food_ledger_qr_raw_material": "0 23 * * 5",
    "sync_food_ledger_qr_storage": "20 23 * * 5",
    "sync_food_ledger_qr_manufacture": "30 23 * * 5",
    "sync_food_ledger_qr_packaging": "40 23 * * 5",
    "sync_food_ledger_qr_caution": "50 23 * * 5",
    "sync_food_ledger_qr_allergy": "0 1 * * 6",
    "sync_food_ledger_qr_nutrition": "30 1 * * 6",
    "sync_food_ledger_production": "0 19 * * 6",
    "sync_food_ledger_livestock_production": "0 19 * * 0",
    "sync_food_ledger_health_functional_production": "0 6 * * 6",
}

BATCH_SCHEDULE = table(
    "batch_schedule",
    column("code", sa.String()),
    column("cron", sa.String()),
)


def _apply(schedule: dict[str, str]) -> None:
    """Write one cron per code, one statement each: the table is the job table."""
    for code, cron in schedule.items():
        op.execute(
            BATCH_SCHEDULE.update().where(BATCH_SCHEDULE.c.code == code).values(cron=cron)
        )


def upgrade() -> None:
    """Upgrade schema."""
    _apply(SCHEDULE)


def downgrade() -> None:
    """Downgrade schema."""
    _apply(PREVIOUS_SCHEDULE)
