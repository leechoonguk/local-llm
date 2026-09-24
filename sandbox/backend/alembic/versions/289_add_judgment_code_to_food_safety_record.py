"""add judgment code to food safety record

The portal's verdict is Korean data - 적합 / 부적합 / 검토중 / 상기와같음, and
blank where it is not published yet - so a screen cannot switch on it: a filter
written against 부적합 is a Korean literal in a component, and a translation of
it no longer matches the row it filters. `judgment_code` is our reading of that
word in three values this codebase owns, and it is what the filter, the count
and the colour use; `judgment` stays exactly as published and is what a reader
sees.

The index moves with the decision: nothing narrows by the Korean word.

`상기와같음` ("as above") reads as `passed` and a blank as `pending` - the
specimen is still out. Filled by the next `derive_food_tables` run, which is
the only writer this table has.

Revision ID: 289
Revises: 288
Create Date: 2026-09-20 01:04:15.267186

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "289"
down_revision: str | Sequence[str] | None = "288"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "food_safety_record", sa.Column("judgment_code", sa.String(length=16), nullable=True)
    )
    op.drop_index(op.f("ix_food_safety_record_judgment"), table_name="food_safety_record")
    op.create_index(
        op.f("ix_food_safety_record_judgment_code"),
        "food_safety_record",
        ["judgment_code"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_food_safety_record_judgment_code",
        "food_safety_record",
        "judgment_code IS NULL OR judgment_code IN ('failed', 'passed', 'pending')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_food_safety_record_judgment_code", "food_safety_record", type_="check")
    op.drop_index(op.f("ix_food_safety_record_judgment_code"), table_name="food_safety_record")
    op.create_index(
        op.f("ix_food_safety_record_judgment"), "food_safety_record", ["judgment"], unique=False
    )
    op.drop_column("food_safety_record", "judgment_code")
