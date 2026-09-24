"""add food allergy derived table

Revision ID: 168
Revises: 167

The split of the HACCP label ledger's comma-joined 알레르기 유발물질: one row
per name, keyed on (품목보고번호, 순번). Measured over the whole feed
(2026-09-12): 14,666 records carry the column, 41 of them exactly `없음`
(dropped - absence is the absence of rows), the rest yielding 28,324 names of
which 476 are distinct.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "168"
down_revision: str | Sequence[str] | None = "167"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_allergy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_by", sa.String(length=50), nullable=True),
        sa.Column("updated_by", sa.String(length=50), nullable=True),
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
        sa.UniqueConstraint("item_report_no", "position", name="uq_food_allergy_natural_key"),
    )
    op.create_index(
        op.f("ix_food_allergy_item_report_no"), "food_allergy", ["item_report_no"], unique=False
    )
    op.create_index("ix_food_allergy_name", "food_allergy", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_food_allergy_name", table_name="food_allergy")
    op.drop_index(op.f("ix_food_allergy_item_report_no"), table_name="food_allergy")
    op.drop_table("food_allergy")
