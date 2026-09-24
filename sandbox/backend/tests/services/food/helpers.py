"""What the food ledger tests share: a feed as the walk hands it over.

A `replace_*_ledger` reads pages, one `Sequence` of records per yield, the
way `IntegrationOperationService.walk_operation` yields them - a test that
handed the service a bare list would be testing a signature the job never
calls.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped


async def pages(*batches: Sequence[object]) -> AsyncIterator[Sequence[object]]:
    """The feed a test scripts: each argument is one page, in order."""
    for batch in batches:
        yield batch


class _Ledger(Protocol):
    id: Mapped[UUID]


async def ledger_rows[T: _Ledger](session: AsyncSession, model: type[T]) -> list[T]:
    """Every row of a ledger, in `id` order - a ledger has no reader of its own.

    The `id` is minted from the natural key (`LedgerStage._row_id`), so the
    order is the key's, stable across passes and hosts.
    """
    return list((await session.execute(select(model).order_by(model.id))).scalars().all())
