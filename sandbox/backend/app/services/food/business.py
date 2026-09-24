# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import re
from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.ledger import LedgerStage, scan_table, synced_columns
from app.models.base import Base
from app.models.food import business as biz
from app.models.food.business import FoodBusiness
from app.models.food.ledger_additive_manufacturing_closure import (
    FoodLedgerAdditiveManufacturingClosure,
)
from app.models.food.ledger_business import FoodLedgerBusiness
from app.models.food.ledger_business_site import FoodLedgerBusinessSite
from app.models.food.ledger_health_functional_closure import (
    FoodLedgerHealthFunctionalClosure,
)
from app.models.food.ledger_import_business_closure import (
    FoodLedgerImportBusinessClosure,
)
from app.models.food.ledger_livestock_processing_closure import (
    FoodLedgerLivestockProcessingClosure,
)
from app.models.food.ledger_manufacturing_closure import FoodLedgerManufacturingClosure
from app.models.food.ledger_meat_packaging_closure import FoodLedgerMeatPackagingClosure
from app.repositories.food.business import FoodBusinessRepository
from app.schemas.food.business import FoodBusinessFacets, FoodBusinessFilter


# ============================================================
# Constants
# ============================================================

# The ledgers are read in pages of this many rows: the master alone is
# 1,548,814 rows, some 1,550 pages, each a keyed index walk.
PAGE_SIZE = 1000

# The key every source ledger carries a business under.
LEDGER_KEY = ("license_no",)

# Every column the model declares beyond its key and the audit trail.
SYNCED_COLUMNS = synced_columns(FoodBusiness, biz.NATURAL_KEY)

# The ten industries this table keeps out of the master's 52 - the ones the
# product registries and the production ledgers report under (live pass
# 2026-09-23: 96,367 live licences; every 품목제조보고 licence is one of these).
INDUSTRIES = frozenset(
    {
        "식품제조가공업",
        "식품제조가공업(주류)",
        "식품첨가물제조업",
        "건강기능식품전문제조업",
        "건강기능식품벤처제조업",
        "축산물가공업-식육가공업",
        "축산물가공업-유가공업",
        "축산물가공업-알가공업",
        "식육포장처리업",
        "수입식품등 수입판매업",
    }
)

# What the master is read for.
MASTER_COLUMNS = ("license_no", "industry_name", "business_name", "permit_date", "district")

# What a closure ledger is read for - the master's columns plus the closure's
# own three. Every closure ledger carries the same nine columns.
CLOSURE_COLUMNS = (
    *MASTER_COLUMNS,
    "closed_date",
    "closure_kind",
    "institution_name",
)

# The six closure ledgers. Each is filtered to INDUSTRIES on its own
# `industry_name`, which drops the 판매업 rows the 건강기능식품 and 수입식품업
# feeds mostly consist of (302,242 of 302,735 and 41,298 of 161,057, live pass
# 2026-09-23).
CLOSURE_LEDGERS = (
    FoodLedgerManufacturingClosure,
    FoodLedgerAdditiveManufacturingClosure,
    FoodLedgerImportBusinessClosure,
    FoodLedgerHealthFunctionalClosure,
    FoodLedgerLivestockProcessingClosure,
    FoodLedgerMeatPackagingClosure,
)

# What the GIS ledger is read for: the two site keys, building first.
SITE_COLUMNS = ("license_no", "building_no", "parcel_code")

# What `name_key` strips: spaces, brackets, and the corporate suffixes the
# registries write inconsistently - `주식회사 오뚜기`, `(주)오뚜기`, `오뚜기㈜`
# are one name to a reader.
# Suffixes first, then the brackets: `(주)` is a suffix as a whole, and taking
# the brackets out first would leave `주` on the name.
_CORPORATE_SUFFIX = re.compile(r"주식회사|\(주\)|（주）|㈜|유한회사|유한책임회사")

_NAME_NOISE = re.compile(r"\s+|[()（）]")


# ============================================================
# Classes
# ============================================================


class FoodBusinessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.business_repository = FoodBusinessRepository(session)

    async def get_business(self, food_business_id: UUID) -> FoodBusiness:
        business = await self.business_repository.get(food_business_id)
        if business is None:
            raise NotFoundError(food_business_id)
        return business

    async def list_businesses(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: FoodBusinessFilter | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> list[FoodBusiness]:
        return await self.business_repository.list(offset, limit, filters, sort, order)

    async def count_businesses(self, filters: FoodBusinessFilter | None = None) -> int:
        return await self.business_repository.count(filters)

    async def list_business_facets(self) -> FoodBusinessFacets:
        """The values the industry select offers: the table's own, read now."""
        return FoodBusinessFacets(
            industry_name=await self.business_repository.distinct_values("industry_name")
        )

    async def list_same_name(self, business: FoodBusiness) -> list[FoodBusiness]:
        """The other rows under this name key; none when the row has no key."""
        if business.name_key is None:
            return []
        return await self.business_repository.list_by_name_key(business.name_key, business.id)

    async def list_same_site(self, business: FoodBusiness) -> list[FoodBusiness]:
        """The other licences on this site; none when the GIS ledger gave the row no key."""
        if business.site_key is None:
            return []
        return await self.business_repository.list_by_site_key(business.site_key, business.id)

    async def rebuild_business(self, synced_by: str) -> int:
        """Write `food_business` as a function of the eight business ledgers; return its rows.

        The master's rows of the ten industries become the live rows, the six
        closure ledgers' rows of the same industries the closed ones - the two
        sets are disjoint by 인허가번호 (measured 2026-09-23), so the state is
        which ledger a row came from and no row is written twice. The GIS
        ledger then lends each row its site key where it has one. Every ledger
        is read whole in keyed pages, the table is assembled in memory (some
        300,000 rows), staged in pages and written over in one short
        transaction (`LedgerStage.replace`, no floor: the ledgers' own floors
        already vouched for the rows this reads).
        """
        stage = LedgerStage(self.session, FoodBusiness, biz.NATURAL_KEY, SYNCED_COLUMNS)
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                rows = await self._assemble()
                for start in range(0, len(rows), PAGE_SIZE):
                    await stage.add(rows[start : start + PAGE_SIZE])
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()

    async def _assemble(self) -> list[dict[str, object]]:
        """Every business row, keyed by 인허가번호, from the eight ledgers."""
        rows: dict[str, dict[str, object]] = {}
        await self._read_live(rows)
        for ledger in CLOSURE_LEDGERS:
            await self._read_closed(ledger, rows)
        await self._lend_sites(rows)
        return list(rows.values())

    async def _read_live(self, rows: dict[str, dict[str, object]]) -> None:
        """The master's rows of the ten industries, as live businesses."""
        async for page in scan_table(
            self.session, FoodLedgerBusiness, LEDGER_KEY, MASTER_COLUMNS, PAGE_SIZE
        ):
            for row in page:
                if row.get("industry_name") in INDUSTRIES:
                    rows[str(row["license_no"])] = _business(row, biz.ACTIVE)

    async def _read_closed(self, ledger: type[Base], rows: dict[str, dict[str, object]]) -> None:
        """One closure ledger's rows of the ten industries, as closed businesses.

        `setdefault`, not assignment: the sets are disjoint on the live feeds,
        and if a portal ever answered a licence on both sides the live reading
        is the one a reader wants.
        """
        async for page in scan_table(self.session, ledger, LEDGER_KEY, CLOSURE_COLUMNS, PAGE_SIZE):
            for row in page:
                if row.get("industry_name") in INDUSTRIES:
                    rows.setdefault(str(row["license_no"]), _business(row, biz.CLOSED))

    async def _lend_sites(self, rows: dict[str, dict[str, object]]) -> None:
        """The GIS ledger's site key on every row that has one: building, else parcel."""
        async for page in scan_table(
            self.session, FoodLedgerBusinessSite, LEDGER_KEY, SITE_COLUMNS, PAGE_SIZE
        ):
            for row in page:
                business = rows.get(str(row["license_no"]))
                if business is not None:
                    business["site_key"] = row.get("building_no") or row.get("parcel_code")


# ============================================================
# Functions
# ============================================================


def _name_key(business_name: object) -> str | None:
    """The name a reader would match on: spaces, brackets and corporate suffixes gone."""
    if not isinstance(business_name, str):
        return None
    key = _NAME_NOISE.sub("", _CORPORATE_SUFFIX.sub("", business_name))
    return key or None


def _business(row: Mapping[str, object], status: str) -> dict[str, object]:
    """The derived row: the ledger's columns under the status its ledger means."""
    return {
        "license_no": row["license_no"],
        "industry_name": row.get("industry_name"),
        "business_name": row.get("business_name"),
        "permit_date": row.get("permit_date"),
        "district": row.get("district"),
        "status": status,
        "closed_date": row.get("closed_date"),
        "closure_kind": row.get("closure_kind"),
        "institution_name": row.get("institution_name"),
        "site_key": None,
        "name_key": _name_key(row.get("business_name")),
    }
