"""schedule every batch job on its measured cadence

The 33 rows carried times nobody had measured against: the crons were written
while the feeds were being built, one at a time, and 298 switched every row off
rather than let them fire. This sets all 33 from the run log - every duration
below is a `batch_run.duration_ms` this database recorded.

**`enabled` is not touched.** 298 made activation an operator's act rather than
a deployment's, and a revision that switched the rows back on would undo that
by starting 33 jobs on the clock of every database it is applied to - a
developer's laptop included. The cron is the schedule and travels with the
code; switching a job on is one `PATCH /batch/{id}` in the environment that
wants it running.

Three facts decide the layout.

**A cron is a Seoul wall clock now.** `settings.scheduler_timezone` is read onto
the trigger, so `0 1 * * *` is 01:00 in Seoul rather than 10:00. The weekday is
written by name (`sat`): APScheduler numbers the week from Monday, so the `5`
these rows used to carry was Saturday and the `6` beside it was Sunday - two
different conventions one keystroke apart.

**A provider is a lane.** `JOB_PROVIDERS` lets one job of a provider walk at a
time, so the 22 `mfds-food-safety-korea` jobs and the 11 `data-go-kr` jobs form
two queues that overlap each other and never themselves. A cron here is
therefore the order a job *enters* its lane, not a promise about when it
starts; the tight spacing inside a weekly group is that order, written down.

**Cadence follows what the feed is, bounded by what a pass costs.**

| Group | Cadence | Why | Measured pass |
|---|---|---|---|
| 회수·검사·행정처분 | daily | events, and a day-old recall is the one that matters | 57m, the rest seconds |
| 품목·표시·기준규격·QR | weekly, Saturday | registrations and reference tables, too big for a night | mfds 7.0h, data-go-kr 2.0h |
| 생산실적 | monthly, nth Monday | annual statistics, and the walk outlives a day | 25.6h / 42.9h / 6m |

The monthly walks are anchored to a Monday (`1-7 * mon` is the first Monday -
APScheduler ANDs the day and the weekday, unlike Vixie cron, which ORs them) so
the two multi-day passes never run into the Saturday groups. What they do run
into is the daily group: on those Mondays the event feeds queue behind the
production walk, and `derive_food_tables` stands down while any dependency is
in flight. That is the design working - a derived table rebuilt mid-walk would
stand a day behind its ledgers - and it costs the derivation one or two days a
month.

`derive_food_tables` is at 04:00, after the daily feeds and before the working
day; the two purges follow it.

The downgrade restores the crons these rows carried. It says nothing about
`enabled` either, for the same reason.

Revision ID: 299
Revises: 298
Create Date: 2026-09-22 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "299"
down_revision: str | Sequence[str] | None = "298"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The schedule, as a Seoul wall clock. Every comment is a measured pass.
SCHEDULE: tuple[tuple[str, str], ...] = (
    # Daily — events, mfds lane, ~1h end to end.
    ("sync_food_ledger_recall", "0 1 * * *"),
    ("sync_food_ledger_inspection_failure", "5 1 * * *"),
    ("sync_food_ledger_admin_disposition", "10 1 * * *"),
    ("sync_food_ledger_collection_inspection", "20 1 * * *"),
    # Daily — the derivation and the two purges, no lane, nobody to wait for.
    ("derive_food_tables", "0 4 * * *"),
    ("purge_expired_refreshes", "30 4 * * *"),
    ("purge_old_batch_runs", "40 4 * * *"),
    # Weekly, Saturday — mfds lane, 7.0h: the queue drains by about noon.
    ("sync_food_ledger_item_report", "0 5 * * sat"),
    ("sync_food_ledger_item_report_raw_material", "10 5 * * sat"),
    ("sync_food_ledger_livestock_item_report_raw_material", "20 5 * * sat"),
    ("sync_food_ledger_barcode", "30 5 * * sat"),
    ("sync_food_ledger_common_standard", "40 5 * * sat"),
    ("sync_food_ledger_common_standard_type", "45 5 * * sat"),
    ("sync_food_ledger_common_standard_exclusion", "50 5 * * sat"),
    ("sync_food_ledger_individual_standard", "55 5 * * sat"),
    ("sync_food_ledger_raw_material", "0 6 * * sat"),
    ("sync_food_ledger_test_item", "5 6 * * sat"),
    ("sync_food_ledger_product_classification", "10 6 * * sat"),
    ("sync_food_ledger_health_functional_item_report", "15 6 * * sat"),
    # Weekly, Saturday — data-go-kr lane, 2.0h, beside the group above.
    ("sync_food_ledger_import_food_label", "0 5 * * sat"),
    ("sync_food_ledger_nutrition", "10 5 * * sat"),
    ("sync_food_ledger_haccp_label", "20 5 * * sat"),
    ("sync_food_ledger_qr_label", "30 5 * * sat"),
    ("sync_food_ledger_qr_raw_material", "35 5 * * sat"),
    ("sync_food_ledger_qr_storage", "40 5 * * sat"),
    ("sync_food_ledger_qr_manufacture", "45 5 * * sat"),
    ("sync_food_ledger_qr_packaging", "50 5 * * sat"),
    ("sync_food_ledger_qr_caution", "55 5 * * sat"),
    ("sync_food_ledger_qr_allergy", "0 6 * * sat"),
    ("sync_food_ledger_qr_nutrition", "5 6 * * sat"),
    # Monthly — the production statistics, on the first, second and third
    # Monday: 25.6h, 42.9h and 6m of walking, kept off the Saturday groups.
    ("sync_food_ledger_production", "0 6 1-7 * mon"),
    ("sync_food_ledger_livestock_production", "0 6 8-14 * mon"),
    ("sync_food_ledger_health_functional_production", "0 6 15-21 * mon"),
)


# What each row carried before this revision, for the way back.
PREVIOUS: tuple[tuple[str, str], ...] = (
    ("derive_food_tables", "0 10 * * *"),
    ("purge_expired_refreshes", "0 3 * * *"),
    ("purge_old_batch_runs", "0 4 * * *"),
    ("sync_food_ledger_admin_disposition", "20 19 * * 5"),
    ("sync_food_ledger_barcode", "0 22 * * 5"),
    ("sync_food_ledger_collection_inspection", "0 19 * * 4"),
    ("sync_food_ledger_common_standard", "0 22 * * 5"),
    ("sync_food_ledger_common_standard_exclusion", "15 19 * * 5"),
    ("sync_food_ledger_common_standard_type", "20 19 * * 5"),
    ("sync_food_ledger_haccp_label", "30 20 * * 0"),
    ("sync_food_ledger_health_functional_item_report", "35 19 * * 5"),
    ("sync_food_ledger_health_functional_production", "0 19 14 * *"),
    ("sync_food_ledger_import_food_label", "0 19 * * 0"),
    ("sync_food_ledger_individual_standard", "0 20 * * 5"),
    ("sync_food_ledger_inspection_failure", "5 19 * * 5"),
    ("sync_food_ledger_item_report", "0 19 * * 6"),
    ("sync_food_ledger_item_report_raw_material", "30 22 * * 6"),
    ("sync_food_ledger_livestock_item_report_raw_material", "0 2 * * 0"),
    ("sync_food_ledger_livestock_production", "0 19 10 * *"),
    ("sync_food_ledger_nutrition", "30 19 * * 0"),
    ("sync_food_ledger_product_classification", "25 19 * * 5"),
    ("sync_food_ledger_production", "0 19 1 * *"),
    ("sync_food_ledger_qr_allergy", "0 22 * * 0"),
    ("sync_food_ledger_qr_caution", "50 21 * * 0"),
    ("sync_food_ledger_qr_label", "0 21 * * 0"),
    ("sync_food_ledger_qr_manufacture", "30 21 * * 0"),
    ("sync_food_ledger_qr_nutrition", "10 22 * * 0"),
    ("sync_food_ledger_qr_packaging", "40 21 * * 0"),
    ("sync_food_ledger_qr_raw_material", "10 21 * * 0"),
    ("sync_food_ledger_qr_storage", "20 21 * * 0"),
    ("sync_food_ledger_raw_material", "45 19 * * 5"),
    ("sync_food_ledger_recall", "0 19 * * 5"),
    ("sync_food_ledger_test_item", "10 19 * * 5"),
)


def _schedules() -> sa.TableClause:
    return sa.table(
        "batch_schedule",
        sa.column("code", sa.String),
        sa.column("cron", sa.String),
    )


def upgrade() -> None:
    """Upgrade schema."""
    schedules = _schedules()
    for code, cron in SCHEDULE:
        op.execute(schedules.update().where(schedules.c.code == code).values(cron=cron))


def downgrade() -> None:
    """Downgrade schema."""
    schedules = _schedules()
    for code, cron in PREVIOUS:
        op.execute(schedules.update().where(schedules.c.code == code).values(cron=cron))
