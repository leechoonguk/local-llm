"""rename food_item_report to food_ledger_item_report

Revision ID: 138
Revises: 137

A ledger carries its own prefix so the bare `food_*` names belong to the tables a
router speaks (rule://backend-relations). PostgreSQL keeps the old names on the
indexes, constraints and primary key of a renamed table, so each one is
recreated under the new table's name here - alembic compares indexes by name,
and a stale `food_<old>_pkey` would make the next table of that name collide
into `..._pkey1`.
"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "138"
down_revision: str | Sequence[str] | None = "137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("food_item_report", "food_ledger_item_report")
    op.drop_constraint("food_item_report_pkey", "food_ledger_item_report", type_="primary")
    op.create_primary_key("food_ledger_item_report_pkey", "food_ledger_item_report", ["id"])
    op.drop_index("ix_food_item_report_item_report_no", table_name="food_ledger_item_report")
    op.create_index("ix_food_ledger_item_report_item_report_no", "food_ledger_item_report", ["item_report_no"], unique=True)
    op.drop_index("ix_food_item_report_license_no", table_name="food_ledger_item_report")
    op.create_index("ix_food_ledger_item_report_license_no", "food_ledger_item_report", ["license_no"], unique=False)
    op.drop_index("ix_food_item_report_source_updated_at", table_name="food_ledger_item_report")
    op.create_index("ix_food_ledger_item_report_source_updated_at", "food_ledger_item_report", ["source_updated_at"], unique=False)


def downgrade() -> None:
    op.rename_table("food_ledger_item_report", "food_item_report")
    op.drop_constraint("food_ledger_item_report_pkey", "food_item_report", type_="primary")
    op.create_primary_key("food_item_report_pkey", "food_item_report", ["id"])
    op.drop_index("ix_food_ledger_item_report_item_report_no", table_name="food_item_report")
    op.create_index("ix_food_item_report_item_report_no", "food_item_report", ["item_report_no"], unique=True)
    op.drop_index("ix_food_ledger_item_report_license_no", table_name="food_item_report")
    op.create_index("ix_food_item_report_license_no", "food_item_report", ["license_no"], unique=False)
    op.drop_index("ix_food_ledger_item_report_source_updated_at", table_name="food_item_report")
    op.create_index("ix_food_item_report_source_updated_at", "food_item_report", ["source_updated_at"], unique=False)
