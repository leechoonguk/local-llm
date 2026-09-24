"""add common standard exclusion derived table

Revision ID: 155
Revises: 154

`food_common_standard_exclusion` - the I2610 ledger read whole into a derived table so that its edges
can be declared on it and not on the ledger (rule://backend-relations); the
derive job rebuilds it. Derived, not fed, so it carries no foreign key.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "155"
down_revision: str | Sequence[str] | None = "154"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "food_common_standard_exclusion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("common_standard_type_code", sa.String(length=32), nullable=False),
        sa.Column("product_code", sa.String(length=32), nullable=False),
        sa.Column("test_item_code", sa.String(length=32), nullable=False),
        sa.Column("standard_name", sa.Text(), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "common_standard_type_code",
            "product_code",
            "test_item_code",
            name="uq_food_common_standard_exclusion_key",
        ),
    )
    op.create_index(
        op.f("ix_food_common_standard_exclusion_common_standard_type_code"),
        "food_common_standard_exclusion",
        ["common_standard_type_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_common_standard_exclusion_product_code"),
        "food_common_standard_exclusion",
        ["product_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_common_standard_exclusion_test_item_code"),
        "food_common_standard_exclusion",
        ["test_item_code"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_food_common_standard_exclusion_test_item_code"),
        table_name="food_common_standard_exclusion",
    )
    op.drop_index(
        op.f("ix_food_common_standard_exclusion_product_code"),
        table_name="food_common_standard_exclusion",
    )
    op.drop_index(
        op.f("ix_food_common_standard_exclusion_common_standard_type_code"),
        table_name="food_common_standard_exclusion",
    )
    op.drop_table("food_common_standard_exclusion")
