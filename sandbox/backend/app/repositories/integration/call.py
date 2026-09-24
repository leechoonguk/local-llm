# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration.call import IntegrationCall
from app.schemas.integration.call import IntegrationCallCreateInternal


# ============================================================
# Classes
# ============================================================


class IntegrationCallRepository:
    """Append-and-read: the log is written once per call and never edited.

    No `update`/`delete` here on purpose — a record of what we sent that
    someone can rewrite answers nothing during an incident.

    Reads are keyed on `provider_code`, not on the provider's id: the log
    outlives the configuration it used (`operation_id` is `SET NULL`), and the
    code is what `ix_integration_call_provider_code_created_at` orders by.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_provider(
        self, provider_code: str, offset: int = 0, limit: int = 100
    ) -> list[IntegrationCall]:
        """One provider's calls, newest first.

        Descending because the question this table answers is "what did we send
        and what came back", and page one must be the call in question.
        """
        result = await self.session.execute(
            select(IntegrationCall)
            .where(IntegrationCall.provider_code == provider_code)
            .order_by(IntegrationCall.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_provider(self, provider_code: str) -> int:
        """How many rows the unwindowed `list_by_provider` would return."""
        result = await self.session.execute(
            select(func.count())
            .select_from(IntegrationCall)
            .where(IntegrationCall.provider_code == provider_code)
        )
        return result.scalar_one()

    async def create(self, data: IntegrationCallCreateInternal) -> IntegrationCall:
        call = IntegrationCall(**data.model_dump())
        self.session.add(call)
        await self.session.flush()
        return call
