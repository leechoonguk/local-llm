"""rename food_nutrition to food_ledger_nutrition

Revision ID: 137
Revises: 136

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
revision: str = "137"
down_revision: str | Sequence[str] | None = "136"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("food_nutrition", "food_ledger_nutrition")
    op.drop_constraint("food_nutrition_pkey", "food_ledger_nutrition", type_="primary")
    op.create_primary_key("food_ledger_nutrition_pkey", "food_ledger_nutrition", ["id"])
    op.drop_index("ix_food_nutrition_food_code", table_name="food_ledger_nutrition")
    op.create_index("ix_food_ledger_nutrition_food_code", "food_ledger_nutrition", ["food_code"], unique=True)
    op.drop_index("ix_food_nutrition_source_updated_at", table_name="food_ledger_nutrition")
    op.create_index("ix_food_ledger_nutrition_source_updated_at", "food_ledger_nutrition", ["source_updated_at"], unique=False)


def downgrade() -> None:
    op.rename_table("food_ledger_nutrition", "food_nutrition")
    op.drop_constraint("food_ledger_nutrition_pkey", "food_nutrition", type_="primary")
    op.create_primary_key("food_nutrition_pkey", "food_nutrition", ["id"])
    op.drop_index("ix_food_ledger_nutrition_food_code", table_name="food_nutrition")
    op.create_index("ix_food_nutrition_food_code", "food_nutrition", ["food_code"], unique=True)
    op.drop_index("ix_food_ledger_nutrition_source_updated_at", table_name="food_nutrition")
    op.create_index("ix_food_nutrition_source_updated_at", "food_nutrition", ["source_updated_at"], unique=False)
