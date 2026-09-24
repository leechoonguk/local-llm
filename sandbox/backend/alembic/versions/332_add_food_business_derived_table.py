"""add food business derived table

One row per licensed food business, live or closed, rebuilt nightly by the
derive job off eight ledgers (I2500 and the six closure feeds for the rows, I2560
for the site key). Live pass 2026-09-23: 96,367 live licences in the ten
industries this project reads, 202,652 closed ones, disjoint by 인허가번호.

The unit is the 인허가, and `name_key` groups rows of one name without
claiming one owner - nothing public keys a licence to a 법인등록번호.

Revision ID: 332
Revises: 331
Create Date: 2026-09-23 07:21:32.338816

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "332"
down_revision: str | Sequence[str] | None = "331"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """The derived table: one row per 인허가번호, the key unique, the name key indexed."""
    op.create_table(
        "food_business",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("license_no", sa.String(length=32), nullable=False),
        sa.Column("industry_name", sa.String(length=120), nullable=True),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("permit_date", sa.String(length=16), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("closed_date", sa.String(length=16), nullable=True),
        sa.Column("closure_kind", sa.String(length=120), nullable=True),
        sa.Column("institution_name", sa.String(length=120), nullable=True),
        sa.Column("site_key", sa.String(length=32), nullable=True),
        sa.Column("name_key", sa.Text(), nullable=True),
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
        "ix_food_business_industry_name", "food_business", ["industry_name"], unique=False
    )
    op.create_index(
        op.f("ix_food_business_license_no"), "food_business", ["license_no"], unique=True
    )
    op.create_index("ix_food_business_name_key", "food_business", ["name_key"], unique=False)


def downgrade() -> None:
    """Drop the derived table."""
    op.drop_index("ix_food_business_name_key", table_name="food_business")
    op.drop_index(op.f("ix_food_business_license_no"), table_name="food_business")
    op.drop_index("ix_food_business_industry_name", table_name="food_business")
    op.drop_table("food_business")
