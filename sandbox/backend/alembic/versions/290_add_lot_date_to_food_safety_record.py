"""add lot date to food safety record

Revision ID: 290
Revises: 289
Create Date: 2026-09-20 13:19:41.368713

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "290"
down_revision: str | Sequence[str] | None = "289"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """The lot an authority acted on, read out of 제조일자 where a date can be read."""
    op.add_column("food_safety_record", sa.Column("lot_date", sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Drop the lot date."""
    op.drop_column("food_safety_record", "lot_date")
