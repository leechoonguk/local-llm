"""rename food_item_report_event to food_safety_record

Revision ID: 288
Revises: 287

The table held only what went wrong - a recall, a failed inspection, a 부적합
수거검사 - under the name 위해정보. That made two different facts look identical
on a screen: a product never sampled and a product sampled twelve times and
clean both read "nothing published". It now holds **every** 수거검사 verdict
beside the actions (2,045,467 + 952 rows), so it is 검사·조치 이력 and its name,
its key and its columns say so:

    food_item_report_event  → food_safety_record
    event_key               → record_key
    event_kind              → record_kind
    event_date              → recorded_on
    (new)                   → judgment

A rename rather than a drop and a create: the rows are the same rows, and one
revision touches one table. PostgreSQL keeps the old names on a renamed table's
indexes, constraints and primary key, so each is recreated here - alembic
compares indexes by name, and a stale `food_item_report_event_pkey` would make
the next table of that name collide into `..._pkey1`.

`judgment` arrives NULL on every existing row and is filled by the next
`derive_food_tables` run, which is the only writer this table has.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "288"
down_revision: str | Sequence[str] | None = "287"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.rename_table("food_item_report_event", "food_safety_record")
    op.alter_column("food_safety_record", "event_key", new_column_name="record_key")
    op.alter_column("food_safety_record", "event_kind", new_column_name="record_kind")
    op.alter_column("food_safety_record", "event_date", new_column_name="recorded_on")
    op.add_column("food_safety_record", sa.Column("judgment", sa.String(length=120), nullable=True))
    op.drop_constraint("food_item_report_event_pkey", "food_safety_record", type_="primary")
    op.create_primary_key("food_safety_record_pkey", "food_safety_record", ["id"])
    op.drop_constraint("uq_food_item_report_event_natural_key", "food_safety_record", type_="unique")
    op.create_unique_constraint("uq_food_safety_record_natural_key", "food_safety_record", ["record_key"])
    op.drop_constraint("ck_food_item_report_event_kind", "food_safety_record", type_="check")
    op.create_check_constraint(
        "ck_food_safety_record_kind",
        "food_safety_record",
        "record_kind IN ('recall', 'inspection_failure', 'collection_inspection')",
    )
    op.drop_index("ix_food_item_report_event_event_date", table_name="food_safety_record")
    op.drop_index("ix_food_item_report_event_report", table_name="food_safety_record")
    op.create_index("ix_food_safety_record_recorded_on", "food_safety_record", ["recorded_on"])
    op.create_index("ix_food_safety_record_record_kind", "food_safety_record", ["record_kind"])
    op.create_index("ix_food_safety_record_judgment", "food_safety_record", ["judgment"])
    op.create_index("ix_food_safety_record_report", "food_safety_record", ["report_kind", "item_report_no"])


def downgrade() -> None:
    op.drop_index("ix_food_safety_record_report", table_name="food_safety_record")
    op.drop_index("ix_food_safety_record_judgment", table_name="food_safety_record")
    op.drop_index("ix_food_safety_record_record_kind", table_name="food_safety_record")
    op.drop_index("ix_food_safety_record_recorded_on", table_name="food_safety_record")
    op.drop_constraint("ck_food_safety_record_kind", "food_safety_record", type_="check")
    op.drop_constraint("uq_food_safety_record_natural_key", "food_safety_record", type_="unique")
    op.drop_column("food_safety_record", "judgment")
    op.alter_column("food_safety_record", "recorded_on", new_column_name="event_date")
    op.alter_column("food_safety_record", "record_kind", new_column_name="event_kind")
    op.alter_column("food_safety_record", "record_key", new_column_name="event_key")
    op.drop_constraint("food_safety_record_pkey", "food_safety_record", type_="primary")
    op.rename_table("food_safety_record", "food_item_report_event")
    op.create_primary_key("food_item_report_event_pkey", "food_item_report_event", ["id"])
    op.create_unique_constraint("uq_food_item_report_event_natural_key", "food_item_report_event", ["event_key"])
    op.create_check_constraint(
        "ck_food_item_report_event_kind",
        "food_item_report_event",
        "event_kind IN ('recall', 'inspection_failure', 'collection_inspection')",
    )
    op.create_index("ix_food_item_report_event_event_date", "food_item_report_event", ["event_date"])
    op.create_index("ix_food_item_report_event_report", "food_item_report_event", ["report_kind", "item_report_no"])
