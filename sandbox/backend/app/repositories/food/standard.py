# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.food import standard as standard_model
from app.models.food.standard import FoodStandard


# ============================================================
# Classes
# ============================================================


class FoodStandardRepository:
    """Reads over the derived 기준규격 table. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_individual_by_product_codes(
        self, product_codes: Sequence[str]
    ) -> list[FoodStandard]:
        """The 제5 clauses written on these types - the caller asks about a type it names."""
        return await self._by_product_codes(standard_model.INDIVIDUAL_KIND, product_codes)

    async def list_common_by_product_codes(
        self, product_codes: Sequence[str]
    ) -> list[FoodStandard]:
        """The 제2 clauses written on these nodes - the caller asks about a whole path.

        Two methods over one query, because the kind is this table's word and not
        the caller's: a service that spelled 'common' would be naming a column
        value of a table it does not own.
        """
        return await self._by_product_codes(standard_model.COMMON_KIND, product_codes)

    async def _by_product_codes(
        self, standard_kind: str, product_codes: Sequence[str]
    ) -> list[FoodStandard]:
        """One chapter's clauses on these nodes, each with its test item.

        Ordered by the node first so a reader sees one node's clauses together;
        `common_standard_type_code` is NULL on every 개별 row and orders nothing
        there.
        """
        if not product_codes:
            return []
        result = await self.session.execute(
            select(FoodStandard)
            .where(
                FoodStandard.standard_kind == standard_kind,
                FoodStandard.product_code.in_(list(product_codes)),
            )
            .options(selectinload(FoodStandard.test_item))
            .order_by(
                FoodStandard.product_code,
                FoodStandard.common_standard_type_code,
                FoodStandard.clause_seq,
                FoodStandard.standard_seq,
            )
        )
        return list(result.scalars().all())
