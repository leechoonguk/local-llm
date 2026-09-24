"""carry the registry kind on food barcode

Revision ID: 265
Revises: 264
Create Date: 2026-09-15

C005 publishes a 품목보고번호 and never says which registry numbered it, while
`food_item_report` is keyed by (report_kind, item_report_no): the edge needs
both columns, so the derive job resolves the kind against the three numbered
report ledgers (measured 2026-09-15: 119,638 of 246,195 rows resolve - domestic
97,686, livestock 13,511, health_functional 8,441).

`permit_date` becomes `report_date` in the same pass: nothing here is a permit,
and the column means 보고일자 as it does on `food_item_report`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "265"
down_revision: str | Sequence[str] | None = "264"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("food_barcode", sa.Column("report_kind", sa.String(length=32), nullable=True))
    op.create_index(
        op.f("ix_food_barcode_report_kind"), "food_barcode", ["report_kind"], unique=False
    )
    op.alter_column("food_barcode", "permit_date", new_column_name="report_date")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("food_barcode", "report_date", new_column_name="permit_date")
    op.drop_index(op.f("ix_food_barcode_report_kind"), table_name="food_barcode")
    op.drop_column("food_barcode", "report_kind")
