"""rebuild food label derived table

Revision ID: 206
Revises: 205

`food_label` is rebuilt for two sources. It was one row per E라벨관리번호 of the
푸드QR 표시사항 feed (2,278 rows); it becomes one row per label of either portal,
keyed (source, label_key) - 푸드QR by E라벨관리번호, HACCP by 품목보고번호.

Measured 2026-09-13: 푸드QR knows 4,765 labels and HACCP 14,664 품목보고번호,
sharing 56 보고 numbers; together they reach 9,750 rows of `food_item_report`
where the 표시사항 feed alone reached 1,911. The two are never merged - on those
56, 제품명 agrees on 34 and 내용량 on 11, because a 품목보고번호 covers several
packages and the portals hold different ones.

The columns the five new 푸드QR feeds fill arrive with it: 보관방법 (2,868 rows),
원재료 텍스트 carrying 함량 and 원산지 (2,301), 업소명·대표자·소재지 (2,976).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "206"
down_revision: str | Sequence[str] | None = "205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rows():
    """The derived table, as a bare row set: nothing here reads a column but the key."""
    return table("food_label", column("id", sa.Uuid()))


def upgrade() -> None:
    # A derived table is a function of the ledgers, so the rows go and the derive
    # job writes them again under the new key; there is nothing here to migrate.
    op.get_bind().execute(_rows().delete())
    op.add_column("food_label", sa.Column("source", sa.String(length=120), nullable=False))
    op.add_column("food_label", sa.Column("label_key", sa.String(length=32), nullable=False))
    op.add_column(
        "food_label", sa.Column("product_type_state", sa.String(length=120), nullable=True)
    )
    op.add_column("food_label", sa.Column("storage_text", sa.Text(), nullable=True))
    op.add_column("food_label", sa.Column("raw_material_text", sa.Text(), nullable=True))
    op.add_column("food_label", sa.Column("business_name", sa.Text(), nullable=True))
    op.add_column("food_label", sa.Column("maker_name", sa.Text(), nullable=True))
    op.add_column("food_label", sa.Column("seller_name", sa.Text(), nullable=True))
    op.add_column(
        "food_label", sa.Column("representative_name", sa.String(length=120), nullable=True)
    )
    op.add_column("food_label", sa.Column("site_address", sa.Text(), nullable=True))
    op.drop_index(op.f("ix_food_label_label_no"), table_name="food_label")
    op.create_index(op.f("ix_food_label_label_key"), "food_label", ["label_key"], unique=False)
    op.create_index(op.f("ix_food_label_source"), "food_label", ["source"], unique=False)
    op.drop_column("food_label", "label_no")
    op.create_unique_constraint("uq_food_label_natural_key", "food_label", ["source", "label_key"])


def downgrade() -> None:
    op.drop_constraint("uq_food_label_natural_key", "food_label", type_="unique")
    op.get_bind().execute(_rows().delete())
    op.add_column(
        "food_label",
        sa.Column("label_no", sa.VARCHAR(length=32), autoincrement=False, nullable=False),
    )
    op.drop_index(op.f("ix_food_label_source"), table_name="food_label")
    op.drop_index(op.f("ix_food_label_label_key"), table_name="food_label")
    op.create_index(op.f("ix_food_label_label_no"), "food_label", ["label_no"], unique=True)
    op.drop_column("food_label", "site_address")
    op.drop_column("food_label", "representative_name")
    op.drop_column("food_label", "seller_name")
    op.drop_column("food_label", "maker_name")
    op.drop_column("food_label", "business_name")
    op.drop_column("food_label", "raw_material_text")
    op.drop_column("food_label", "storage_text")
    op.drop_column("food_label", "product_type_state")
    op.drop_column("food_label", "label_key")
    op.drop_column("food_label", "source")
