"""rebuild food label allergen derived table

Revision ID: 207
Revises: 206

The allergen split follows its label onto (source, label_key, position).

It gains the HACCP feed: 19,802 rows over 6,115 products, where `알수없음`
(8,484 values) and `없음` (41) become no row at all. With 푸드QR's 8,441
label-name pairs that is 28,243 rows against today's 8,580 (2026-09-13).

`serial` goes: it was the 푸드QR 일련번호, and a row's position within its label
is what a reader orders by.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "207"
down_revision: str | Sequence[str] | None = "206"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rows():
    """The derived table, as a bare row set: nothing here reads a column but the key."""
    return table("food_label_allergen", column("id", sa.Uuid()))


def upgrade() -> None:
    # Same reason as the label table: the rows are rebuilt, never migrated.
    op.get_bind().execute(_rows().delete())
    op.add_column("food_label_allergen", sa.Column("source", sa.String(length=120), nullable=False))
    op.add_column(
        "food_label_allergen", sa.Column("label_key", sa.String(length=32), nullable=False)
    )
    op.drop_index(op.f("ix_food_label_allergen_label_no"), table_name="food_label_allergen")
    op.drop_constraint(
        op.f("uq_food_label_allergen_natural_key"), "food_label_allergen", type_="unique"
    )
    op.create_index(
        op.f("ix_food_label_allergen_label_key"), "food_label_allergen", ["label_key"], unique=False
    )
    op.drop_column("food_label_allergen", "serial")
    op.drop_column("food_label_allergen", "label_no")
    op.create_unique_constraint(
        "uq_food_label_allergen_natural_key",
        "food_label_allergen",
        ["source", "label_key", "position"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_food_label_allergen_natural_key", "food_label_allergen", type_="unique"
    )
    op.get_bind().execute(_rows().delete())
    op.add_column(
        "food_label_allergen",
        sa.Column("label_no", sa.VARCHAR(length=32), autoincrement=False, nullable=False),
    )
    op.add_column(
        "food_label_allergen",
        sa.Column("serial", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
    )
    op.drop_index(op.f("ix_food_label_allergen_label_key"), table_name="food_label_allergen")
    op.create_unique_constraint(
        op.f("uq_food_label_allergen_natural_key"),
        "food_label_allergen",
        ["label_no", "position"],
        postgresql_nulls_not_distinct=False,
    )
    op.create_index(
        op.f("ix_food_label_allergen_label_no"), "food_label_allergen", ["label_no"], unique=False
    )
    op.drop_column("food_label_allergen", "label_key")
    op.drop_column("food_label_allergen", "source")
