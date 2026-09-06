"""What the food ledger tests share: a feed as the walk hands it over.

A `replace_*_ledger` reads pages, one `Sequence` of records per yield, the
way `IntegrationOperationService.walk_operation` yields them - a test that
handed the service a bare list would be testing a signature the job never
calls.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence


async def pages(*batches: Sequence[object]) -> AsyncIterator[Sequence[object]]:
    """The feed a test scripts: each argument is one page, in order."""
    for batch in batches:
        yield batch
