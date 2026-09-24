"""rename food_common_standard_type to food_ledger_common_standard_type

Revision ID: 143
Revises: 142

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
revision: str = "143"
down_revision: str | Sequence[str] | None = "142"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("food_common_standard_type", "food_ledger_common_standard_type")
    op.drop_constraint("food_common_standard_type_pkey", "food_ledger_common_standard_type", type_="primary")
    op.create_primary_key("food_ledger_common_standard_type_pkey", "food_ledger_common_standard_type", ["id"])
    op.drop_index("ix_food_common_standard_type_common_standard_type_code", table_name="food_ledger_common_standard_type")
    op.create_index("ix_food_ledger_common_standard_type_common_standard_type_code", "food_ledger_common_standard_type", ["common_standard_type_code"], unique=True)
    op.drop_index("ix_food_common_standard_type_parent_common_standard_type_code", table_name="food_ledger_common_standard_type")
    op.create_index("ix_food_ledger_common_standard_type_parent_code", "food_ledger_common_standard_type", ["parent_common_standard_type_code"], unique=False)
    op.drop_index("ix_food_common_standard_type_source_updated_at", table_name="food_ledger_common_standard_type")
    op.create_index("ix_food_ledger_common_standard_type_source_updated_at", "food_ledger_common_standard_type", ["source_updated_at"], unique=False)


def downgrade() -> None:
    op.rename_table("food_ledger_common_standard_type", "food_common_standard_type")
    op.drop_constraint("food_ledger_common_standard_type_pkey", "food_common_standard_type", type_="primary")
    op.create_primary_key("food_common_standard_type_pkey", "food_common_standard_type", ["id"])
    op.drop_index("ix_food_ledger_common_standard_type_common_standard_type_code", table_name="food_common_standard_type")
    op.create_index("ix_food_common_standard_type_common_standard_type_code", "food_common_standard_type", ["common_standard_type_code"], unique=True)
    op.drop_index("ix_food_ledger_common_standard_type_parent_code", table_name="food_common_standard_type")
    op.create_index("ix_food_common_standard_type_parent_common_standard_type_code", "food_common_standard_type", ["parent_common_standard_type_code"], unique=False)
    op.drop_index("ix_food_ledger_common_standard_type_source_updated_at", table_name="food_common_standard_type")
    op.create_index("ix_food_common_standard_type_source_updated_at", "food_common_standard_type", ["source_updated_at"], unique=False)
