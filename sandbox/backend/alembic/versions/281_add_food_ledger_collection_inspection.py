"""add food ledger collection inspection table

The ledger of 식품안전나라 I0460 (수거검사 결과) - 2,046,194 rows spanning
수거일자 20000214~20260917 (2026-09-18), the largest feed this project reads.

Keyed on `record_digest`, a sha256 of all twelve published columns, because the
feed publishes no identifier: 수거증번호 repeats 651,739 times and every
composite of the twelve repeats too. Even the whole record repeats - 1,037 rows
of the portal's own snapshot are identical in all twelve values - and two rows
identical in every published column are indistinguishable to a reader, so
collapsing them loses nothing.

Three indexes, each earning its build time on a table rewritten whole every
pass: `item_report_no` is the only column that reaches a product (filled on
32.6 % of rows), `judgment` because 부적합 is 0.43 % of the feed (8,861 rows) and
is the only reason to read it, and `collected_on` because every reading of "what
was found when" orders by it.

Revision ID: 281
Revises: 280
Create Date: 2026-09-18 23:56:22.291372

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "281"
down_revision: str | Sequence[str] | None = "280"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "food_ledger_collection_inspection",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column("collection_no", sa.Text(), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("industry_name", sa.String(length=120), nullable=True),
        sa.Column("specimen_type", sa.String(length=120), nullable=True),
        sa.Column("collected_on", sa.String(length=32), nullable=True),
        sa.Column("judgment", sa.String(length=120), nullable=True),
        sa.Column("institution_name", sa.Text(), nullable=True),
        sa.Column("item_report_no", sa.String(length=32), nullable=True),
        sa.Column("plan_title", sa.Text(), nullable=True),
        sa.Column("source_updated_text", sa.String(length=120), nullable=True),
        sa.Column("created_by", sa.String(length=80), nullable=True),
        sa.Column("updated_by", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "record_digest", name="uq_food_ledger_collection_inspection_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_ledger_collection_inspection_collected_on"),
        "food_ledger_collection_inspection",
        ["collected_on"],
        unique=False,
    )
    op.create_index(
        "ix_food_ledger_collection_inspection_item_report_no",
        "food_ledger_collection_inspection",
        ["item_report_no"],
        unique=False,
    )
    op.create_index(
        "ix_food_ledger_collection_inspection_judgment",
        "food_ledger_collection_inspection",
        ["judgment"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_food_ledger_collection_inspection_judgment",
        table_name="food_ledger_collection_inspection",
    )
    op.drop_index(
        "ix_food_ledger_collection_inspection_item_report_no",
        table_name="food_ledger_collection_inspection",
    )
    op.drop_index(
        op.f("ix_food_ledger_collection_inspection_collected_on"),
        table_name="food_ledger_collection_inspection",
    )
    op.drop_table("food_ledger_collection_inspection")
