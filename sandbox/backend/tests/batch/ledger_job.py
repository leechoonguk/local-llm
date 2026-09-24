"""What every ledger job's test asserts, once.

A ledger job is four constants and one call; the body it delegates to is
`sync_ledger`, tested in `tests/services/batch/test_ledger_feed.py`. What is
this job's own is the wiring - which operation it walks, which ledger that walk
fills, and that the rows say this job wrote them - and that is what a test per
job reads.

The records are the operation's own recorded fixture (`tests/core/fixtures/
integration/<operation>.json`, the canonical payload the contract check
records), so a test never invents a provider record.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import app.services.batch.ledger_feed as ledger_feed
from tests.batch.scripted import (
    rows,
    run_in_context,
    script_walk,
    steps,
    swapped_engine,
)


FIXTURES = Path(__file__).resolve().parents[1] / "core" / "fixtures" / "integration"


def canonical_records(operation: str) -> list[dict[str, Any]]:
    """The records that operation answered when its contract was recorded."""
    fixture = json.loads((FIXTURES / f"{operation}.json").read_text(encoding="utf-8"))
    expected = fixture["expect"]
    # A file operation's execute answers the download and its rows are what
    # stream read (`expect.rows`); a paged one's canonical payload is its page.
    return list(expected.get("rows") or expected["canonical_payload"])


async def assert_job_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
    job,
    module,
    model,
) -> None:
    """Run one ledger job against a scripted walk of its own feed.

    The walk answers one short page, which is where a pass ends; the ledger
    then holds that page, stamped with the job's `SYNCED_BY`, and the run has
    one step per window asked for. Whether the service publishes one flat
    sequence or one set per coordinate is configuration, not the job's - the
    walk asks the operation row - so this scripts the flat shape and the
    coordinate's own contract is the runner's test.
    """
    records = canonical_records(module.FEED.operation_code)
    async with swapped_engine(ledger_feed) as engine:
        asked = script_walk(
            monkeypatch,
            "RANGE" if module.END_CODES else "PAGE",
            {module.FEED.operation_code: [records]},
            page_size=module.PAGE_SIZE,
        )
        await run_in_context(engine, module.SYNCED_BY)

        written = await job()

        assert written == len(await rows(engine, model)) > 0
        assert [operation for operation, _ in asked] == [module.FEED.operation_code]
        assert [step.sequence for step in await steps(engine)] == [1]
        assert {row.created_by for row in await rows(engine, model)} == {module.SYNCED_BY}
