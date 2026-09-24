"""rename food_product_classification to food_ledger_product_classification

Revision ID: 140
Revises: 139

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
revision: str = "140"
down_revision: str | Sequence[str] | None = "139"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("food_product_classification", "food_ledger_product_classification")
    op.drop_constraint("food_product_classification_pkey", "food_ledger_product_classification", type_="primary")
    op.create_primary_key("food_ledger_product_classification_pkey", "food_ledger_product_classification", ["id"])
    op.drop_index("ix_food_product_classification_parent_product_code", table_name="food_ledger_product_classification")
    op.create_index("ix_food_ledger_product_classification_parent_product_code", "food_ledger_product_classification", ["parent_product_code"], unique=False)
    op.drop_index("ix_food_product_classification_product_code", table_name="food_ledger_product_classification")
    op.create_index("ix_food_ledger_product_classification_product_code", "food_ledger_product_classification", ["product_code"], unique=True)
    op.drop_index("ix_food_product_classification_source_updated_at", table_name="food_ledger_product_classification")
    op.create_index("ix_food_ledger_product_classification_source_updated_at", "food_ledger_product_classification", ["source_updated_at"], unique=False)


def downgrade() -> None:
    op.rename_table("food_ledger_product_classification", "food_product_classification")
    op.drop_constraint("food_ledger_product_classification_pkey", "food_product_classification", type_="primary")
    op.create_primary_key("food_product_classification_pkey", "food_product_classification", ["id"])
    op.drop_index("ix_food_ledger_product_classification_parent_product_code", table_name="food_product_classification")
    op.create_index("ix_food_product_classification_parent_product_code", "food_product_classification", ["parent_product_code"], unique=False)
    op.drop_index("ix_food_ledger_product_classification_product_code", table_name="food_product_classification")
    op.create_index("ix_food_product_classification_product_code", "food_product_classification", ["product_code"], unique=True)
    op.drop_index("ix_food_ledger_product_classification_source_updated_at", table_name="food_product_classification")
    op.create_index("ix_food_product_classification_source_updated_at", "food_product_classification", ["source_updated_at"], unique=False)
