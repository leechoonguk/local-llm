"""carry the registry kind on food label

Revision ID: 266
Revises: 265
Create Date: 2026-09-15

A label points at a product by (report_kind, item_report_no) like every other
child of `food_item_report`. An import label needs no lookup - this repository
numbered it - and the 푸드QR and HACCP labels are resolved against the numbered
registries (measured 2026-09-15: 8,033 domestic, 1,938 livestock, 49
health_functional of the 16,938 that name a number).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "266"
down_revision: str | Sequence[str] | None = "265"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("food_label", sa.Column("report_kind", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_food_label_report_kind"), "food_label", ["report_kind"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_food_label_report_kind"), table_name="food_label")
    op.drop_column("food_label", "report_kind")
