"""food raw material synonyms are text

이명·영문명·학명 are synonym *lists*: the portal joins every alias it knows into
one comma-separated string, and its length is an editorial choice nobody
publishes. Measured over the whole feed (2026-09-05, 43,609 records): alias 1130,
scientific 311, english 272 — against 94/225/242 in the first 3000 rows. A bound
was tried at 200 and again at 1000, and the feed exceeded both further down; each
rejection cost a whole page, because an INSERT that fails takes the window with
it. `Text` stores identically to `VARCHAR` in Postgres, so the bound bought
nothing but the outage.

Revision ID: 96
Revises: 95
Create Date: 2026-09-05 09:55:37.596141

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "95"
down_revision: str | Sequence[str] | None = "94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    for name in ("raw_material_alias", "english_name", "scientific_name"):
        op.alter_column(
            "food_raw_material",
            name,
            existing_type=sa.VARCHAR(length=200),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    for name in ("scientific_name", "english_name", "raw_material_alias"):
        op.alter_column(
            "food_raw_material",
            name,
            existing_type=sa.Text(),
            type_=sa.VARCHAR(length=200),
            existing_nullable=True,
        )
