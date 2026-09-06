"""rename barcode ledger to food_barcode

Autogenerate proposed `drop_table` + `create_table`, which would have emptied the
ledger: the rows are a synced copy that costs a full re-run of the provider's
windows to rebuild. A rename keeps them. The four sibling ledgers coming from the
same 식품안전나라 services group under the same prefix afterwards, the way
`integration_*` and `batch_*` already do.

Postgres carries constraint and index names through a table rename, so each one
is recreated under the new prefix. The primary key keeps its generated name
(`barcode_pkey`): renaming it needs raw SQL, which an unpushed revision may not
use (backend-migrations.md), and nothing addresses that name.

Revision ID: 91
Revises: 90
Create Date: 2026-09-05 09:00:58.440902

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "91"
down_revision: str | Sequence[str] | None = "90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NATURAL_KEY = ["barcode_no", "report_no"]


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("barcode", "food_barcode")
    op.drop_constraint("uq_barcode_barcode_no_report_no", "food_barcode", type_="unique")
    op.create_unique_constraint(
        "uq_food_barcode_barcode_no_report_no", "food_barcode", NATURAL_KEY
    )
    op.drop_index("ix_barcode_report_no", table_name="food_barcode")
    op.create_index("ix_food_barcode_report_no", "food_barcode", ["report_no"])
    op.drop_index("ix_barcode_source_updated_at", table_name="food_barcode")
    op.create_index("ix_food_barcode_source_updated_at", "food_barcode", ["source_updated_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_food_barcode_source_updated_at", table_name="food_barcode")
    op.create_index("ix_barcode_source_updated_at", "food_barcode", ["source_updated_at"])
    op.drop_index("ix_food_barcode_report_no", table_name="food_barcode")
    op.create_index("ix_barcode_report_no", "food_barcode", ["report_no"])
    op.drop_constraint("uq_food_barcode_barcode_no_report_no", "food_barcode", type_="unique")
    op.create_unique_constraint("uq_barcode_barcode_no_report_no", "food_barcode", NATURAL_KEY)
    op.rename_table("food_barcode", "barcode")
