"""drop food individual standard

Revision ID: 264
Revises: 263
Create Date: 2026-09-15

Its rows are `food_standard` rows under `standard_kind = 'individual'` from
revision 262 - the same merge, the other chapter.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "264"
down_revision: str | Sequence[str] | None = "263"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(
        op.f("ix_food_individual_standard_individual_standard_seq"),
        table_name="food_individual_standard",
    )
    op.drop_index(
        op.f("ix_food_individual_standard_product_code"), table_name="food_individual_standard"
    )
    op.drop_index(
        op.f("ix_food_individual_standard_test_item_code"), table_name="food_individual_standard"
    )
    op.drop_table("food_individual_standard")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "food_individual_standard",
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "individual_standard_seq", sa.VARCHAR(length=32), autoincrement=False, nullable=False
        ),
        sa.Column("test_item_code", sa.VARCHAR(length=32), autoincrement=False, nullable=False),
        sa.Column("detail_item_name", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("clause_seq", sa.VARCHAR(length=32), autoincrement=False, nullable=False),
        sa.Column("product_code", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("product_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("test_item_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("clause_name", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("standard_value", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("standard_value_summary", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("valid_begin_date", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("valid_end_date", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("source_code", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("valid_digits", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column(
            "judgment_format_code", sa.VARCHAR(length=32), autoincrement=False, nullable=True
        ),
        sa.Column(
            "judgment_format_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True
        ),
        sa.Column("maximum_value", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column(
            "maximum_value_type_code", sa.VARCHAR(length=32), autoincrement=False, nullable=True
        ),
        sa.Column(
            "maximum_value_type_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True
        ),
        sa.Column("minimum_value", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column(
            "minimum_value_type_code", sa.VARCHAR(length=32), autoincrement=False, nullable=True
        ),
        sa.Column(
            "minimum_value_type_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True
        ),
        sa.Column("choice_fit_code", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("choice_fit_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("choice_unfit_code", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("choice_unfit_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("microbe_2n", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("microbe_2c", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("microbe_2m", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("microbe_3m", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column(
            "detail_item_included_yn", sa.VARCHAR(length=20), autoincrement=False, nullable=True
        ),
        sa.Column("hazard_yn", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column(
            "priority_inspection_yn", sa.VARCHAR(length=20), autoincrement=False, nullable=True
        ),
        sa.Column("monitoring_yn", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("outside_codex_yn", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("self_inspection_yn", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("unit_code", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("unit_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("update_reason", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column(
            "source_updated_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("created_by", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column("updated_by", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.INTEGER(),
            server_default=sa.text("1"),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("food_individual_standard_pkey")),
        sa.UniqueConstraint(
            "individual_standard_seq",
            "test_item_code",
            "detail_item_name",
            "clause_seq",
            name=op.f("uq_food_individual_standard_natural_key"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        op.f("ix_food_individual_standard_test_item_code"),
        "food_individual_standard",
        ["test_item_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_individual_standard_product_code"),
        "food_individual_standard",
        ["product_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_individual_standard_individual_standard_seq"),
        "food_individual_standard",
        ["individual_standard_seq"],
        unique=False,
    )
