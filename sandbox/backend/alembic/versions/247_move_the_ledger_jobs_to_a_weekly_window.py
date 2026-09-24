"""move the ledger jobs to a weekly window

Revision ID: 247
Revises: 246

The nightly window does not hold the feeds any more, and the arithmetic says so
(measured 2026-09-15, `decks/ledger-measurements` §2-§3):

    mfds feeds as they stand      2,739 windows, ~3.5 h
    생산실적 I0300 (year-split)    7,933 windows, ~5.7 h
    생산실적 I1420 (year-split)    3,403 windows, ~8.5 h
    생산실적 I0310 (year-split)      321 windows, ~0.1 h
    ------------------------------------------------------
    one mfds pass                 ~17.8 h, ~20 h with the derive job behind it

The old layout gave the two provider jobs 00:00 and 01:00 with
`derive_food_tables` at 10:00 - ten hours, which ~20 h overruns. A whole pass is
not negotiable (a ledger *is* its feed, rule://backend-ledger), and the feeds
that forced the size are reported once a year, so the cadence moves instead of
the contract:

    sync_mfds_ledgers          Friday 20:00 KST   (weekly)
    sync_data_go_kr_ledgers    Friday 20:00 KST   (weekly, ~1 h 52 m measured)
    derive_food_tables         Sunday 10:00 KST   (after both, weekly)

식품안전나라 is shut 09:00-19:00 KST (`ERROR-503`, measured 2026-09-15), so its
~18 h of walking is not 18 h of clock: Friday 20:00 buys 13 hours, the job
sleeps out Saturday's working day on the quota machinery (revision 258) and
finishes in Saturday night's hours. The derive job fires Sunday 10:00, after
both nights, and skips with a log line while a dependency is still running.

data.go.kr has no such window and finishes inside Friday night. A feed that
failed is next week's, as it was next night's before - or an operator's
`POST /batch/{id}/run`, which needs nothing new.

The three rows keep their ids; only the cron moves.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "247"
down_revision: str | Sequence[str] | None = "246"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MFDS_JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-mfds-ledgers")
DATA_GO_KR_JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-data-go-kr-ledgers")
DERIVE_JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/derive-food-tables")
# (id, cron) - the weekly layout, and what each row was before it.
WEEKLY: list[tuple[UUID, str]] = [
    (MFDS_JOB_ID, "0 20 * * 5"),
    (DATA_GO_KR_JOB_ID, "0 20 * * 5"),
    (DERIVE_JOB_ID, "0 10 * * 0"),
]

NIGHTLY: list[tuple[UUID, str]] = [
    (MFDS_JOB_ID, "0 0 * * *"),
    (DATA_GO_KR_JOB_ID, "0 1 * * *"),
    (DERIVE_JOB_ID, "0 10 * * *"),
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


def _move(layout: list[tuple[UUID, str]]) -> None:
    schedules = _schedules()
    bind = op.get_bind()
    for job_id, cron in layout:
        bind.execute(schedules.update().where(schedules.c.id == job_id).values(cron=cron))


def upgrade() -> None:
    """Upgrade schema."""
    _move(WEEKLY)


def downgrade() -> None:
    """Downgrade schema."""
    _move(NIGHTLY)
