"""drop the daytime block from the integration operation quota

Revision ID: 260
Revises: 259
Create Date: 2026-09-15

Revision 258 read 식품안전나라's `ERROR-503` as a quota with a ten-hour window,
so a walk that met it slept until the service reopened. With one job per ledger
(revision 259) there is nothing to sleep for: a job's whole night is inside
19:00-09:00, and a job that meets the block has met it because it overran its
night. Waiting ten hours would have it walking through the next working day and
into the next job's slot.

So the block is an ordinary failure again: the run ends FAILED with the
portal's own message, the ledger stays last week's, and the next week's row -
or an operator's `POST /batch/{id}/run` after 19:00 - walks it.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "260"
down_revision: str | Sequence[str] | None = "259"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_CODE = "mfds-food-safety-korea"

PROVIDER_ID = uuid5(NAMESPACE_URL, f"fast-api-standard/{PROVIDER_CODE}/provider")

DAYTIME_BLOCK_CODE = "ERROR-503"

DAYTIME_BLOCK_WINDOW = 36000


def _operations() -> sa.TableClause:
    return table(
        "integration_operation",
        column("id", sa.Uuid()),
        column("provider_id", sa.Uuid()),
        column("quota_codes", sa.JSON()),
    )


def _rewrite(add: bool) -> None:
    bind = op.get_bind()
    operations = _operations()
    rows = bind.execute(
        sa.select(operations.c.id, operations.c.quota_codes).where(
            operations.c.provider_id == PROVIDER_ID
        )
    ).all()
    for operation_id, quota_codes in rows:
        codes = dict(quota_codes or {})
        if add:
            codes[DAYTIME_BLOCK_CODE] = DAYTIME_BLOCK_WINDOW
        else:
            codes.pop(DAYTIME_BLOCK_CODE, None)
        bind.execute(
            operations.update().where(operations.c.id == operation_id).values(quota_codes=codes)
        )


def upgrade() -> None:
    """Upgrade schema."""
    _rewrite(add=False)


def downgrade() -> None:
    """Downgrade schema."""
    _rewrite(add=True)
