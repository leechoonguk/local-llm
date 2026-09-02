# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.integration.field import IntegrationField
from app.models.integration.operation import IntegrationOperation
from app.models.integration.provider import Integration


# ============================================================
# Classes
# ============================================================


class IntegrationOperationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_operation(
        self, provider_code: str, operation_code: str
    ) -> IntegrationOperation | None:
        result = await self.session.execute(
            select(IntegrationOperation)
            .join(IntegrationOperation.provider)
            .where(
                Integration.code == provider_code,
                IntegrationOperation.code == operation_code,
            )
            .options(
                selectinload(IntegrationOperation.provider),
                selectinload(IntegrationOperation.fields).selectinload(IntegrationField.secret),
            )
        )
        return result.scalar_one_or_none()
