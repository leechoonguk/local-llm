"""allow collection inspection event kind

`food_item_report_event` held two kinds, 회수 and 검사부적합. 수거검사 부적합 is
the third, and it is the largest: 8,862 rows of I0460's 2,046,504 (2026-09-18),
carrying 1,867 distinct 품목제조보고번호 of which 1,039 are in
`food_item_report` - and only 115 of those numbers had any event before it.

A CHECK is the vocabulary, so widening it is the change; the rows follow from
the next `derive_food_tables` run, which reads the ledger this kind comes from.

Revision ID: 284
Revises: 283

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "284"
down_revision: str | Sequence[str] | None = "283"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_food_item_report_event_kind"

WIDENED = "event_kind IN ('recall', 'inspection_failure', 'collection_inspection')"
PREVIOUS = "event_kind IN ('recall', 'inspection_failure')"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, "food_item_report_event", type_="check")
    op.create_check_constraint(CONSTRAINT, "food_item_report_event", WIDENED)


def downgrade() -> None:
    # The rows of the kind being removed go with it: a narrower vocabulary that
    # left them behind could not be applied at all.
    events = table("food_item_report_event", column("event_kind", sa.String()))
    op.get_bind().execute(events.delete().where(events.c.event_kind == "collection_inspection"))
    op.drop_constraint(CONSTRAINT, "food_item_report_event", type_="check")
    op.create_check_constraint(CONSTRAINT, "food_item_report_event", PREVIOUS)
