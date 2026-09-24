"""add common standard type derived table

Revision ID: 152
Revises: 151

`food_common_standard_type` - the I2590 ledger read whole into a derived table so that its edges
can be declared on it and not on the ledger (rule://backend-relations); the
derive job rebuilds it. Derived, not fed, so it carries no foreign key.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "152"
down_revision: str | Sequence[str] | None = "151"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "food_common_standard_type",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("common_standard_type_code", sa.String(length=32), nullable=False),
        sa.Column("standard_name", sa.String(length=120), nullable=True),
        sa.Column("parent_common_standard_type_code", sa.String(length=32), nullable=True),
        sa.Column("level", sa.String(length=20), nullable=True),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("use_yn", sa.String(length=20), nullable=True),
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
    )
    op.create_index(
        op.f("ix_food_common_standard_type_common_standard_type_code"),
        "food_common_standard_type",
        ["common_standard_type_code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_food_common_standard_type_parent_common_standard_type_code"),
        "food_common_standard_type",
        ["parent_common_standard_type_code"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_food_common_standard_type_parent_common_standard_type_code"),
        table_name="food_common_standard_type",
    )
    op.drop_index(
        op.f("ix_food_common_standard_type_common_standard_type_code"),
        table_name="food_common_standard_type",
    )
    op.drop_table("food_common_standard_type")
