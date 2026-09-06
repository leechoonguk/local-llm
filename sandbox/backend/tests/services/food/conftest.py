"""A session pinned to one connection, which is what a ledger replacement needs.

The stage a pass fills is a TEMP table, and a TEMP table lives on the
connection that created it - `LedgerStage` refuses a session bound to an
engine. The CRUD tests keep using `factory`; only the `replace_*_ledger`
calls need this.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.fixture()
def pinned(engine: AsyncEngine) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    """A context manager opening a session that keeps one connection for its life."""

    @asynccontextmanager
    async def _pinned() -> AsyncIterator[AsyncSession]:
        async with (
            engine.connect() as connection,
            AsyncSession(connection, expire_on_commit=False) as session,
        ):
            yield session

    return _pinned
