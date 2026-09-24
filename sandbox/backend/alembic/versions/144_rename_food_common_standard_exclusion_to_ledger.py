"""rename food_common_standard_exclusion to food_ledger_common_standard_exclusion

Revision ID: 144
Revises: 143

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
revision: str = "144"
down_revision: str | Sequence[str] | None = "143"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("food_common_standard_exclusion", "food_ledger_common_standard_exclusion")
    op.drop_constraint("food_common_standard_exclusion_pkey", "food_ledger_common_standard_exclusion", type_="primary")
    op.create_primary_key("food_ledger_common_standard_exclusion_pkey", "food_ledger_common_standard_exclusion", ["id"])
    op.drop_index("ix_food_common_standard_exclusion_product_code", table_name="food_ledger_common_standard_exclusion")
    op.create_index("ix_food_ledger_common_standard_exclusion_product_code", "food_ledger_common_standard_exclusion", ["product_code"], unique=False)
    op.drop_index("ix_food_common_standard_exclusion_source_updated_at", table_name="food_ledger_common_standard_exclusion")
    op.create_index("ix_food_ledger_common_standard_exclusion_source_updated_at", "food_ledger_common_standard_exclusion", ["source_updated_at"], unique=False)
    op.drop_index("ix_food_common_standard_exclusion_test_item_code", table_name="food_ledger_common_standard_exclusion")
    op.create_index("ix_food_ledger_common_standard_exclusion_test_item_code", "food_ledger_common_standard_exclusion", ["test_item_code"], unique=False)
    op.drop_index("ix_food_common_standard_exclusion_common_standard_type_code", table_name="food_ledger_common_standard_exclusion")
    op.create_index("ix_food_ledger_common_standard_exclusion_type_code", "food_ledger_common_standard_exclusion", ["common_standard_type_code"], unique=False)
    op.drop_constraint("uq_food_common_standard_exclusion_key", "food_ledger_common_standard_exclusion", type_="unique")
    op.create_unique_constraint("uq_food_ledger_common_standard_exclusion_key", "food_ledger_common_standard_exclusion", ["common_standard_type_code", "product_code", "test_item_code"])


def downgrade() -> None:
    op.rename_table("food_ledger_common_standard_exclusion", "food_common_standard_exclusion")
    op.drop_constraint("food_ledger_common_standard_exclusion_pkey", "food_common_standard_exclusion", type_="primary")
    op.create_primary_key("food_common_standard_exclusion_pkey", "food_common_standard_exclusion", ["id"])
    op.drop_index("ix_food_ledger_common_standard_exclusion_product_code", table_name="food_common_standard_exclusion")
    op.create_index("ix_food_common_standard_exclusion_product_code", "food_common_standard_exclusion", ["product_code"], unique=False)
    op.drop_index("ix_food_ledger_common_standard_exclusion_source_updated_at", table_name="food_common_standard_exclusion")
    op.create_index("ix_food_common_standard_exclusion_source_updated_at", "food_common_standard_exclusion", ["source_updated_at"], unique=False)
    op.drop_index("ix_food_ledger_common_standard_exclusion_test_item_code", table_name="food_common_standard_exclusion")
    op.create_index("ix_food_common_standard_exclusion_test_item_code", "food_common_standard_exclusion", ["test_item_code"], unique=False)
    op.drop_index("ix_food_ledger_common_standard_exclusion_type_code", table_name="food_common_standard_exclusion")
    op.create_index("ix_food_common_standard_exclusion_common_standard_type_code", "food_common_standard_exclusion", ["common_standard_type_code"], unique=False)
    op.drop_constraint("uq_food_ledger_common_standard_exclusion_key", "food_common_standard_exclusion", type_="unique")
    op.create_unique_constraint("uq_food_common_standard_exclusion_key", "food_common_standard_exclusion", ["common_standard_type_code", "product_code", "test_item_code"])
