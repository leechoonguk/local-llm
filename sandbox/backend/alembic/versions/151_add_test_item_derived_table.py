"""add test item derived table

Revision ID: 151
Revises: 150

`food_test_item` - the I2570 ledger read whole into a derived table so that its edges
can be declared on it and not on the ledger (rule://backend-relations); the
derive job rebuilds it. Derived, not fed, so it carries no foreign key.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "151"
down_revision: str | Sequence[str] | None = "150"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "food_test_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("test_item_code", sa.String(length=32), nullable=False),
        sa.Column("korean_name", sa.Text(), nullable=True),
        sa.Column("english_name", sa.Text(), nullable=True),
        sa.Column("abbreviation", sa.Text(), nullable=True),
        sa.Column("alias", sa.Text(), nullable=True),
        sa.Column("test_item_name", sa.Text(), nullable=True),
        sa.Column("major_class_sequence", sa.String(length=32), nullable=True),
        sa.Column("major_class_code", sa.String(length=32), nullable=True),
        sa.Column("major_class_korean_name", sa.String(length=120), nullable=True),
        sa.Column("middle_class_sequence", sa.String(length=32), nullable=True),
        sa.Column("middle_class_code", sa.String(length=32), nullable=True),
        sa.Column("middle_class_korean_name", sa.String(length=120), nullable=True),
        sa.Column("residue_definition", sa.Text(), nullable=True),
        sa.Column("in_use", sa.String(length=4), nullable=True),
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
        op.f("ix_food_test_item_test_item_code"), "food_test_item", ["test_item_code"], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_food_test_item_test_item_code"), table_name="food_test_item")
    op.drop_table("food_test_item")
