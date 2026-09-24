"""drop food allergy derived table

Revision ID: 171
Revises: 170

The same retirement, one revision per table. Measured before dropping it
(2026-09-12): 28,324 rows over 14,620 products, of which 8,507 (30.0 %) read
`알수없음` or a variant, plus sentences (`대두)에 민감한 반응이 있으신 분은…`)
and `함유` suffixes splitting one allergen into four values. 푸드QR answers one
row per declared allergen.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "171"
down_revision: str | Sequence[str] | None = "170"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_food_allergy_item_report_no"), table_name="food_allergy")
    op.drop_index(op.f("ix_food_allergy_name"), table_name="food_allergy")
    op.drop_table("food_allergy")


def downgrade() -> None:
    op.create_table(
        "food_allergy",
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("item_report_no", sa.VARCHAR(length=32), autoincrement=False, nullable=False),
        sa.Column("position", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=120), autoincrement=False, nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("food_allergy_pkey")),
        sa.UniqueConstraint(
            "item_report_no",
            "position",
            name=op.f("uq_food_allergy_natural_key"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(op.f("ix_food_allergy_name"), "food_allergy", ["name"], unique=False)
    op.create_index(
        op.f("ix_food_allergy_item_report_no"), "food_allergy", ["item_report_no"], unique=False
    )
