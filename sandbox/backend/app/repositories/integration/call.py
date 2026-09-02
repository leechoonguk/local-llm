# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration.call import IntegrationCall
from app.schemas.integration.call import IntegrationCallCreateInternal


# ============================================================
# Classes
# ============================================================


class IntegrationCallRepository:
    """Insert-only: the log is written once per call and never edited.

    No `update`/`delete` here on purpose — a record of what we sent that
    someone can rewrite answers nothing during an incident.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: IntegrationCallCreateInternal) -> IntegrationCall:
        call = IntegrationCall(**data.model_dump())
        self.session.add(call)
        await self.session.flush()
        return call
