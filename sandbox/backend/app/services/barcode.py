# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.barcode import Barcode
from app.repositories.barcode import BarcodeRepository
from app.schemas.barcode import (
    BarcodeCreateInternal,
    BarcodeCreateRequest,
    BarcodeUpdateInternal,
    BarcodeUpdateRequest,
)


# ============================================================
# Constants
# ============================================================

# The columns a stored row and an incoming record are compared on. The natural
# key is excluded: it is what matched them in the first place.
SYNCED_COLUMNS = (
    "report_item_name",
    "product_name",
    "company_name",
    "upper_product_classification_name",
    "top_product_classification_name",
    "source_updated_at",
)


# ============================================================
# Classes
# ============================================================


class BarcodeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.barcode_repository = BarcodeRepository(session)

    async def get_barcode(self, barcode_id: UUID) -> Barcode:
        barcode = await self.barcode_repository.get(barcode_id)
        if barcode is None:
            raise NotFoundError(barcode_id)
        return barcode

    async def list_barcodes(self, offset: int = 0, limit: int = 100) -> list[Barcode]:
        return await self.barcode_repository.list(offset, limit)

    async def create_barcode(self, data: BarcodeCreateRequest, created_by: str) -> Barcode:
        internal = BarcodeCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            return await self.barcode_repository.create(internal)

    async def update_barcode(
        self, barcode_id: UUID, data: BarcodeUpdateRequest, updated_by: str
    ) -> Barcode:
        internal = BarcodeUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            barcode = await self.barcode_repository.update(barcode_id, internal)
            if barcode is None:
                raise NotFoundError(barcode_id)
            return barcode

    async def update_barcode_ledger(
        self, payload: dict[str, object] | list[object], synced_by: str
    ) -> tuple[int, int]:
        """Upsert one page of I2570 records; return (records read, rows written).

        The two numbers answer different questions and the caller needs both:
        the page's length says whether another window exists, and the written
        count says what actually changed. They differ on every run after the
        first, because a window overlapping the cursor re-sends records the
        ledger already holds — those are matched, compared, and left alone
        rather than rewritten, so `updated_at` and `version` keep meaning "this
        record changed" instead of "the batch ran".

        One transaction per page: a page is the unit the provider hands over,
        so a failure halfway through it leaves no half-imported window.
        """
        records = payload if isinstance(payload, list) else [payload]
        written = 0
        async with self.session.begin():
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                data = BarcodeCreateRequest.from_record(record)
                if data is None:
                    continue
                if await self._upsert(data, synced_by):
                    written += 1
        return len(records), written

    async def delete_barcode(self, barcode_id: UUID) -> None:
        async with self.session.begin():
            if not await self.barcode_repository.delete(barcode_id):
                raise NotFoundError(barcode_id)

    async def _upsert(self, data: BarcodeCreateRequest, synced_by: str) -> bool:
        """Insert or refresh one record; report whether a row was written.

        Runs inside the caller's transaction — a page is one boundary, and a
        per-record one would leave the window half applied.
        """
        existing = await self.barcode_repository.get_by_natural_key(data.barcode_no, data.report_no)
        if existing is None:
            await self.barcode_repository.create(
                BarcodeCreateInternal(**data.model_dump(), created_by=synced_by)
            )
            return True
        changes: dict[str, Any] = {}
        for column in SYNCED_COLUMNS:
            stored = getattr(existing, column)
            # SQLite hands `DateTime(timezone=True)` back without its offset, and
            # the column is written in UTC — without this every re-read window
            # would compare unequal and rewrite rows nothing changed about.
            if isinstance(stored, datetime) and stored.tzinfo is None:
                stored = stored.replace(tzinfo=UTC)
            incoming = getattr(data, column)
            if incoming != stored:
                changes[column] = incoming
        if not changes:
            return False
        await self.barcode_repository.update(
            existing.id, BarcodeUpdateInternal(**changes, updated_by=synced_by)
        )
        return True
