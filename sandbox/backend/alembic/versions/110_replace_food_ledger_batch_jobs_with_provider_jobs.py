"""replace the five food ledger batch jobs with one job per provider

Five schedules, one per ledger, each resuming from a cursor of its own, become
two, one per provider, each reading its feeds whole every night: the feeds
carry no change stamp to follow and their `total_count` lies, so a cursor was
bookkeeping over a full pass that happened anyway. A job that reads a whole
feed has nothing to resume, and one job per provider is one paging family and
one end rule per job (`sync_mfds_ledgers`, `sync_data_go_kr_ledgers`).

The old rows are removed by `code`, not by id: the barcode row was seeded under
one id (revision 82) and renamed (92), and the code is what the scheduler keys
on. The new rows take the hours the portals allow — 식품안전나라 at 00:00, a
full pass of its four feeds being ~2,200 windows at 100 calls an hour per key
over three keys (~7.5 h, 2026-09-06); data.go.kr at 01:00, its one feed being
639 windows of 500 with no hourly quota to wait on.

Revision ID: 110
Revises: 109
Create Date: 2026-09-06 12:20:00.000000

"""

from collections.abc import Sequence

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "110"
down_revision: str | Sequence[str] | None = "109"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MFDS_JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-mfds-ledgers")
DATA_GO_KR_JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-data-go-kr-ledgers")

# The rows this revision retires, as revisions 82/92, 94, 97, 100 and 109 wrote
# them - the downgrade puts them back under their own ids.
RETIRED_JOBS = [
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-barcode-ledger"),
        "code": "sync_food_barcode_ledger",
        "name": "Sync food barcode item ledger",
        "description": (
            "Migrates 식품바코드 품목정보(I2570) records into the food_barcode ledger, "
            "resuming from the row cursor the previous run left."
        ),
        "cron": "0 2 * * *",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-raw-material-ledger"),
        "code": "sync_food_raw_material_ledger",
        "name": "Sync food raw material ledger",
        "description": (
            "Migrates 식품 원재료(I2520) records into the food_raw_material ledger, "
            "resuming from the row cursor the previous run left."
        ),
        "cron": "0 3 * * *",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-nutrition-ledger"),
        "code": "sync_food_nutrition_ledger",
        "name": "Sync food nutrition ledger",
        "description": (
            "Migrates 식품 영양성분(I2790) records into the food_nutrition ledger, "
            "resuming from the page cursor the previous run left."
        ),
        "cron": "0 5 * * *",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-item-report-ledger"),
        "code": "sync_food_item_report_ledger",
        "name": "Sync food item report ledger",
        "description": (
            "Migrates 식품(첨가물) 품목제조보고(I1250) records into the food_item_report "
            "ledger, resuming from the row cursor the previous run left."
        ),
        "cron": "0 1 * * *",
    },
    {
        "id": uuid5(
            NAMESPACE_URL, "fast-api-standard/batch/sync-food-item-report-raw-material-ledger"
        ),
        "code": "sync_food_item_report_raw_material_ledger",
        "name": "Sync food item report raw material ledger",
        "description": (
            "Migrates 식품(첨가물) 품목제조보고(원재료)(C002) records into the "
            "food_item_report_raw_material ledger, resuming from the row cursor "
            "the previous run left."
        ),
        "cron": "0 0 * * *",
    },
]

PROVIDER_JOBS = [
    {
        "id": MFDS_JOB_ID,
        "code": "sync_mfds_ledgers",
        "name": "Sync 식품안전나라 ledgers",
        "description": (
            "Replaces the food_barcode, food_raw_material, food_item_report and "
            "food_item_report_raw_material ledgers with a whole pass of their "
            "식품안전나라 feeds (I2570, I2520, I1250, C002)."
        ),
        "cron": "0 0 * * *",
    },
    {
        "id": DATA_GO_KR_JOB_ID,
        "code": "sync_data_go_kr_ledgers",
        "name": "Sync data.go.kr ledgers",
        "description": (
            "Replaces the food_nutrition ledger with a whole pass of its "
            "data.go.kr feed (I2790)."
        ),
        "cron": "0 1 * * *",
    },
]


def _schedules() -> sa.TableClause:
    return table(
        "batch_schedule",
        column("id", sa.Uuid()),
        column("code", sa.String()),
        column("name", sa.String()),
        column("description", sa.String()),
        column("cron", sa.String()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def _seed(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {**row, "enabled": True, "created_by": "migration", "updated_by": "migration"}
        for row in rows
    ]


def upgrade() -> None:
    """Upgrade schema."""
    schedules = _schedules()
    op.execute(
        schedules.delete().where(schedules.c.code.in_([job["code"] for job in RETIRED_JOBS]))
    )
    op.bulk_insert(schedules, _seed(PROVIDER_JOBS))


def downgrade() -> None:
    """Downgrade schema."""
    schedules = _schedules()
    op.execute(
        schedules.delete().where(schedules.c.code.in_([job["code"] for job in PROVIDER_JOBS]))
    )
    op.bulk_insert(schedules, _seed(RETIRED_JOBS))
