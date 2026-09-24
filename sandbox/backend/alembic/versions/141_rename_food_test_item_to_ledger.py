"""rename food_test_item to food_ledger_test_item

Revision ID: 141
Revises: 140

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
revision: str = "141"
down_revision: str | Sequence[str] | None = "140"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("food_test_item", "food_ledger_test_item")
    op.drop_constraint("food_test_item_pkey", "food_ledger_test_item", type_="primary")
    op.create_primary_key("food_ledger_test_item_pkey", "food_ledger_test_item", ["id"])
    op.drop_index("ix_food_test_item_source_updated_at", table_name="food_ledger_test_item")
    op.create_index("ix_food_ledger_test_item_source_updated_at", "food_ledger_test_item", ["source_updated_at"], unique=False)
    op.drop_index("ix_food_test_item_test_item_code", table_name="food_ledger_test_item")
    op.create_index("ix_food_ledger_test_item_test_item_code", "food_ledger_test_item", ["test_item_code"], unique=True)


def downgrade() -> None:
    op.rename_table("food_ledger_test_item", "food_test_item")
    op.drop_constraint("food_ledger_test_item_pkey", "food_test_item", type_="primary")
    op.create_primary_key("food_test_item_pkey", "food_test_item", ["id"])
    op.drop_index("ix_food_ledger_test_item_source_updated_at", table_name="food_test_item")
    op.create_index("ix_food_test_item_source_updated_at", "food_test_item", ["source_updated_at"], unique=False)
    op.drop_index("ix_food_ledger_test_item_test_item_code", table_name="food_test_item")
    op.create_index("ix_food_test_item_test_item_code", "food_test_item", ["test_item_code"], unique=True)
