"""rename food_individual_standard to food_ledger_individual_standard

Revision ID: 146
Revises: 145

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
revision: str = "146"
down_revision: str | Sequence[str] | None = "145"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("food_individual_standard", "food_ledger_individual_standard")
    op.drop_constraint("food_individual_standard_pkey", "food_ledger_individual_standard", type_="primary")
    op.create_primary_key("food_ledger_individual_standard_pkey", "food_ledger_individual_standard", ["id"])
    op.drop_index("ix_food_individual_standard_individual_standard_seq", table_name="food_ledger_individual_standard")
    op.create_index("ix_food_ledger_individual_standard_individual_standard_seq", "food_ledger_individual_standard", ["individual_standard_seq"], unique=False)
    op.drop_index("ix_food_individual_standard_product_code", table_name="food_ledger_individual_standard")
    op.create_index("ix_food_ledger_individual_standard_product_code", "food_ledger_individual_standard", ["product_code"], unique=False)
    op.drop_index("ix_food_individual_standard_source_updated_at", table_name="food_ledger_individual_standard")
    op.create_index("ix_food_ledger_individual_standard_source_updated_at", "food_ledger_individual_standard", ["source_updated_at"], unique=False)
    op.drop_index("ix_food_individual_standard_test_item_code", table_name="food_ledger_individual_standard")
    op.create_index("ix_food_ledger_individual_standard_test_item_code", "food_ledger_individual_standard", ["test_item_code"], unique=False)
    op.drop_constraint("uq_food_individual_standard_natural_key", "food_ledger_individual_standard", type_="unique")
    op.create_unique_constraint("uq_food_ledger_individual_standard_natural_key", "food_ledger_individual_standard", ["individual_standard_seq", "test_item_code", "detail_item_name", "clause_seq"])


def downgrade() -> None:
    op.rename_table("food_ledger_individual_standard", "food_individual_standard")
    op.drop_constraint("food_ledger_individual_standard_pkey", "food_individual_standard", type_="primary")
    op.create_primary_key("food_individual_standard_pkey", "food_individual_standard", ["id"])
    op.drop_index("ix_food_ledger_individual_standard_individual_standard_seq", table_name="food_individual_standard")
    op.create_index("ix_food_individual_standard_individual_standard_seq", "food_individual_standard", ["individual_standard_seq"], unique=False)
    op.drop_index("ix_food_ledger_individual_standard_product_code", table_name="food_individual_standard")
    op.create_index("ix_food_individual_standard_product_code", "food_individual_standard", ["product_code"], unique=False)
    op.drop_index("ix_food_ledger_individual_standard_source_updated_at", table_name="food_individual_standard")
    op.create_index("ix_food_individual_standard_source_updated_at", "food_individual_standard", ["source_updated_at"], unique=False)
    op.drop_index("ix_food_ledger_individual_standard_test_item_code", table_name="food_individual_standard")
    op.create_index("ix_food_individual_standard_test_item_code", "food_individual_standard", ["test_item_code"], unique=False)
    op.drop_constraint("uq_food_ledger_individual_standard_natural_key", "food_individual_standard", type_="unique")
    op.create_unique_constraint("uq_food_individual_standard_natural_key", "food_individual_standard", ["individual_standard_seq", "test_item_code", "detail_item_name", "clause_seq"])
