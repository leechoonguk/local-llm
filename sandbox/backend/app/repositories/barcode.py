# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.barcode import Barcode
from app.schemas.barcode import BarcodeCreateInternal, BarcodeUpdateInternal


# ============================================================
# Classes
# ============================================================


class BarcodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, barcode_id: UUID) -> Barcode | None:
        return await self.session.get(Barcode, barcode_id)

    async def get_by_natural_key(self, barcode_no: str, report_no: str) -> Barcode | None:
        """The row the provider's record refers to, by the pair it is keyed on.

        The sync has no ids of its own: the only thing an incoming record and a
        stored row share is `(barcode_no, report_no)`, which is why that pair
        carries a unique constraint rather than merely an index.
        """
        result = await self.session.execute(
            select(Barcode).where(
                Barcode.barcode_no == barcode_no,
                Barcode.report_no == report_no,
            )
        )
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 100) -> list[Barcode]:
        result = await self.session.execute(select(Barcode).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def create(self, data: BarcodeCreateInternal) -> Barcode:
        barcode = Barcode(**data.model_dump())
        self.session.add(barcode)
        await self.session.flush()
        return barcode

    async def update(self, barcode_id: UUID, data: BarcodeUpdateInternal) -> Barcode | None:
        barcode = await self.session.get(Barcode, barcode_id)
        if barcode is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(barcode, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        barcode.updated_at = datetime.now(UTC)
        await self.session.flush()
        return barcode

    async def delete(self, barcode_id: UUID) -> bool:
        barcode = await self.session.get(Barcode, barcode_id)
        if barcode is None:
            return False
        await self.session.delete(barcode)
        return True
