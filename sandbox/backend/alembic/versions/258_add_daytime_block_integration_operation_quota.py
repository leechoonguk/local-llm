"""add daytime block quota code to mfds operations

Revision ID: 258
Revises: 257
Create Date: 2026-09-15

식품안전나라 is shut during its own working day. Measured 2026-09-15: a walk
that started at 06:57 was refused at 09:00:16, mid-feed, on window 520 of
공통기준규격, with

    ERROR-503  09시~19시에는 서비스가 제한됩니다. 이용에 참고바랍니다.

and every call after it - nine more feeds, all three keys - answered the same
inside two seconds. Read as an ordinary refusal it fails a feed a second; read
as a quota it is what it is, a service that comes back at a known time.

So `ERROR-503` joins `quota_codes` on every operation of this provider, with
the length of the shut period for its window: **36,000 seconds**. The walk then
does what it does for any quota - sleeps, keeps its connection and its stage,
and asks for the same window again. Ten hours is the whole 09:00-19:00 block,
which is what a walk that meets it at 09:00 has to wait; a walk that meets it
later waits past 19:00 and asks again then, one window later than it could
have. That is the price of not computing a time of day, and this repository
pays it: the weekly run starts Friday 20:00 and meets the block at 09:00.

Four operations already listed it under a fixed hour (the 기준규격 family,
revisions 122-133); this revision makes it one meaning for the whole provider.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "258"
down_revision: str | Sequence[str] | None = "257"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_CODE = "mfds-food-safety-korea"

# The id revision 64 seeded, computed the way every seed computes it, so this
# revision reads and writes one table.
PROVIDER_ID = uuid5(NAMESPACE_URL, f"fast-api-standard/{PROVIDER_CODE}/provider")

# What the portal's own message names: shut from 09:00, back at 19:00 KST.
DAYTIME_BLOCK_CODE = "ERROR-503"

# The window, in the vocabulary `quota_codes` already speaks: seconds. Ten
# hours is 09:00 to 19:00 KST, the whole of the shut period.
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
    _rewrite(add=True)


def downgrade() -> None:
    """Downgrade schema."""
    _rewrite(add=False)
