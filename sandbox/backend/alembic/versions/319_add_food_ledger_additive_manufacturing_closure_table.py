"""add food ledger additive manufacturing closure table

The ledger of 식품첨가물제조업 폐업정보 (I2813): 1,707 rows in the file of
2026-09-23, one per 인허가번호. The columns are the file's, one for one, minus
the ones the schema declines (UNSTORED_KEYS); bounds are measured widths.

Revision ID: 319
Revises: 318
Create Date: 2026-09-23 07:17:46.155730

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "319"
down_revision: str | Sequence[str] | None = "318"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """The ledger's table: one row per 인허가번호, the key unique."""
    op.create_table(
        "food_ledger_additive_manufacturing_closure",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("license_no", sa.String(length=32), nullable=False),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("industry_name", sa.String(length=120), nullable=True),
        sa.Column("permit_date", sa.String(length=16), nullable=True),
        sa.Column("closed_date", sa.String(length=16), nullable=True),
        sa.Column("closure_kind", sa.String(length=120), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("institution_name", sa.String(length=120), nullable=True),
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
    )
    op.create_index(
        op.f("ix_food_ledger_additive_manufacturing_closure_license_no"),
        "food_ledger_additive_manufacturing_closure",
        ["license_no"],
        unique=True,
    )


def downgrade() -> None:
    """Drop the ledger."""
    op.drop_index(
        op.f("ix_food_ledger_additive_manufacturing_closure_license_no"),
        table_name="food_ledger_additive_manufacturing_closure",
    )
    op.drop_table("food_ledger_additive_manufacturing_closure")
