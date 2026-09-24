"""add common standard derived table

Revision ID: 154
Revises: 153

`food_common_standard` - the I2600 ledger read whole into a derived table so that its edges
can be declared on it and not on the ledger (rule://backend-relations); the
derive job rebuilds it. Derived, not fed, so it carries no foreign key.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "154"
down_revision: str | Sequence[str] | None = "153"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "food_common_standard",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("common_standard_seq", sa.String(length=32), nullable=False),
        sa.Column("test_item_code", sa.String(length=32), nullable=False),
        sa.Column("common_standard_type_code", sa.String(length=32), nullable=True),
        sa.Column("common_standard_type_name", sa.String(length=120), nullable=True),
        sa.Column("product_code", sa.String(length=32), nullable=True),
        sa.Column("product_name", sa.String(length=120), nullable=True),
        sa.Column("test_item_name", sa.String(length=120), nullable=True),
        sa.Column("detail_item_name", sa.Text(), nullable=True),
        sa.Column("clause_seq", sa.String(length=32), nullable=True),
        sa.Column("clause_name", sa.Text(), nullable=True),
        sa.Column("standard_value", sa.Text(), nullable=True),
        sa.Column("standard_value_summary", sa.Text(), nullable=True),
        sa.Column("valid_begin_date", sa.String(length=20), nullable=True),
        sa.Column("valid_end_date", sa.String(length=20), nullable=True),
        sa.Column("source_code", sa.Text(), nullable=True),
        sa.Column("valid_digits", sa.String(length=32), nullable=True),
        sa.Column("judgment_format_code", sa.String(length=32), nullable=True),
        sa.Column("judgment_format_name", sa.String(length=120), nullable=True),
        sa.Column("maximum_value", sa.String(length=120), nullable=True),
        sa.Column("maximum_value_type_code", sa.String(length=32), nullable=True),
        sa.Column("maximum_value_type_name", sa.String(length=120), nullable=True),
        sa.Column("minimum_value", sa.String(length=120), nullable=True),
        sa.Column("minimum_value_type_code", sa.String(length=32), nullable=True),
        sa.Column("minimum_value_type_name", sa.String(length=120), nullable=True),
        sa.Column("choice_fit_code", sa.String(length=32), nullable=True),
        sa.Column("choice_fit_name", sa.String(length=120), nullable=True),
        sa.Column("choice_unfit_code", sa.String(length=32), nullable=True),
        sa.Column("choice_unfit_name", sa.String(length=120), nullable=True),
        sa.Column("microbe_2n", sa.String(length=20), nullable=True),
        sa.Column("microbe_2c", sa.String(length=20), nullable=True),
        sa.Column("microbe_2m", sa.String(length=20), nullable=True),
        sa.Column("microbe_3m", sa.String(length=20), nullable=True),
        sa.Column("detail_item_included_yn", sa.String(length=20), nullable=True),
        sa.Column("hazard_yn", sa.String(length=20), nullable=True),
        sa.Column("priority_inspection_yn", sa.String(length=20), nullable=True),
        sa.Column("monitoring_yn", sa.String(length=20), nullable=True),
        sa.Column("outside_codex_yn", sa.String(length=20), nullable=True),
        sa.Column("self_inspection_yn", sa.String(length=20), nullable=True),
        sa.Column("unit_code", sa.String(length=32), nullable=True),
        sa.Column("unit_name", sa.String(length=120), nullable=True),
        sa.Column("update_reason", sa.Text(), nullable=True),
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
            "common_standard_seq", "test_item_code", name="uq_food_common_standard_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_common_standard_common_standard_seq"),
        "food_common_standard",
        ["common_standard_seq"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_common_standard_common_standard_type_code"),
        "food_common_standard",
        ["common_standard_type_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_common_standard_product_code"),
        "food_common_standard",
        ["product_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_common_standard_test_item_code"),
        "food_common_standard",
        ["test_item_code"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_food_common_standard_test_item_code"), table_name="food_common_standard")
    op.drop_index(op.f("ix_food_common_standard_product_code"), table_name="food_common_standard")
    op.drop_index(
        op.f("ix_food_common_standard_common_standard_type_code"), table_name="food_common_standard"
    )
    op.drop_index(
        op.f("ix_food_common_standard_common_standard_seq"), table_name="food_common_standard"
    )
    op.drop_table("food_common_standard")
