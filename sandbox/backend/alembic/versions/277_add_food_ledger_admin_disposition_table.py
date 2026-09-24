"""add food ledger admin disposition table

The ledger of 식품안전나라 I0480 (행정처분결과·식품제조가공업): 251 rows over the
whole feed (2026-09-18), keyed on 행정처분전산키. Indexed on `license_no`, the
only column that joins a disposition to a product's maker, and on `decided_on`,
which every reading of "what was published when" orders by.

Revision ID: 277
Revises: 276
Create Date: 2026-09-18 21:59:25.503209

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "277"
down_revision: str | Sequence[str] | None = "276"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "food_ledger_admin_disposition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("disposition_seq", sa.String(length=32), nullable=False),
        sa.Column("license_no", sa.String(length=32), nullable=True),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("industry_name", sa.String(length=120), nullable=True),
        sa.Column("decided_on", sa.String(length=32), nullable=True),
        sa.Column("began_on", sa.String(length=32), nullable=True),
        sa.Column("ended_on", sa.String(length=32), nullable=True),
        sa.Column("disposition_type", sa.String(length=120), nullable=True),
        sa.Column("violation_text", sa.Text(), nullable=True),
        sa.Column("disposition_text", sa.Text(), nullable=True),
        sa.Column("law_text", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("telephone", sa.Text(), nullable=True),
        sa.Column("president_name", sa.Text(), nullable=True),
        sa.Column("institution_name", sa.String(length=120), nullable=True),
        sa.Column("public_until", sa.String(length=120), nullable=True),
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
        sa.UniqueConstraint("disposition_seq", name="uq_food_ledger_admin_disposition_natural_key"),
    )
    op.create_index(
        op.f("ix_food_ledger_admin_disposition_decided_on"),
        "food_ledger_admin_disposition",
        ["decided_on"],
        unique=False,
    )
    op.create_index(
        "ix_food_ledger_admin_disposition_license_no",
        "food_ledger_admin_disposition",
        ["license_no"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_food_ledger_admin_disposition_license_no", table_name="food_ledger_admin_disposition"
    )
    op.drop_index(
        op.f("ix_food_ledger_admin_disposition_decided_on"),
        table_name="food_ledger_admin_disposition",
    )
    op.drop_table("food_ledger_admin_disposition")
