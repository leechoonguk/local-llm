"""checkpoint position is not always a row

`next_range_start` / `last_row_key` were named while every ledger walked rows.
The nutrition ledger pages by page number and stores the page it imported, plus
the *first* record of that page — so both names lied about what a third of the
table's rows hold.

Autogenerate proposed `drop_column` + `add_column`, which would have thrown away
every cursor in the table: four sources, one of them 639 pages deep. A rename
keeps them.

Revision ID: 98
Revises: 97
Create Date: 2026-09-05 12:37:04.661285

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "98"
down_revision: str | Sequence[str] | None = "97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("batch_checkpoint", "next_range_start", new_column_name="resume_position")
    op.alter_column("batch_checkpoint", "last_row_key", new_column_name="resume_key")
    op.drop_constraint(
        op.f("ck_batch_checkpoint_next_range_start"), "batch_checkpoint", type_="check"
    )
    op.create_check_constraint(
        "ck_batch_checkpoint_resume_position", "batch_checkpoint", "resume_position >= 1"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_batch_checkpoint_resume_position", "batch_checkpoint", type_="check")
    op.create_check_constraint(
        op.f("ck_batch_checkpoint_next_range_start"), "batch_checkpoint", "next_range_start >= 1"
    )
    op.alter_column("batch_checkpoint", "resume_key", new_column_name="last_row_key")
    op.alter_column("batch_checkpoint", "resume_position", new_column_name="next_range_start")
