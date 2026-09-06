"""rename sync barcode ledger job to sync_food_barcode_ledger

The schedule is data (revision 82), so renaming the job in Python alone would
leave every environment running a row whose `code` names a module that no longer
exists — the scheduler skips such a row with a warning and the ledger silently
stops syncing. `batch_schedule.code` is the job's identity: the module, the
function, the `BATCH_JOBS` key and this column are one chain, and the ledger it
fills is now `food_barcode`.

The run history is untouched: `batch_run` rows point at the schedule's id, not
its code, so last night's failure still reads against the same row.

Revision ID: 92
Revises: 91
Create Date: 2026-09-05 09:10:14.354152

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "92"
down_revision: str | Sequence[str] | None = "91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    schedules = sa.table(
        "batch_schedule",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
    )
    op.execute(
        schedules.update()
        .where(schedules.c.code == "sync_barcode_ledger")
        .values(
            code="sync_food_barcode_ledger",
            name="Sync food barcode item ledger",
            description=(
                "Migrates 식품바코드 품목정보(I2570) records into the food_barcode ledger, "
                "resuming from the row cursor the previous run left."
            ),
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    schedules = sa.table(
        "batch_schedule",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
    )
    op.execute(
        schedules.update()
        .where(schedules.c.code == "sync_food_barcode_ledger")
        .values(
            code="sync_barcode_ledger",
            name="Sync barcode item ledger",
            description=(
                "Migrates 식품바코드 품목정보(I2570) records into the barcode ledger, "
                "resuming from the row cursor the previous run left."
            ),
        )
    )
