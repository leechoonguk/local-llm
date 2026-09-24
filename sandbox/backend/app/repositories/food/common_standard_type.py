# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.common_standard_type import FoodCommonStandardType


# ============================================================
# Classes
# ============================================================


class FoodCommonStandardTypeRepository:
    """Reads over the derived 공전 outline. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_heading_paths(
        self, type_codes: Sequence[str]
    ) -> dict[str, list[FoodCommonStandardType]]:
        """Each heading's path from the 공전's top down to itself, top first.

        The outline is eight levels deep (90 headings, 2026-09-08), so the walk
        up `parent_common_standard_type_code` is a recursive CTE rather than
        eight edge hops - spelled by column here for the same reason the
        classification tree's is.
        """
        if not type_codes:
            return {}
        heading = FoodCommonStandardType
        seed = (
            select(
                heading.common_standard_type_code.label("origin"),
                heading.common_standard_type_code,
                heading.parent_common_standard_type_code,
            )
            .where(heading.common_standard_type_code.in_(list(type_codes)))
            .cte("outline", recursive=True)
        )
        step = select(
            seed.c.origin,
            heading.common_standard_type_code,
            heading.parent_common_standard_type_code,
        ).join(seed, seed.c.parent_common_standard_type_code == heading.common_standard_type_code)
        outline = seed.union_all(step)
        rows = (
            await self.session.execute(
                select(outline.c.origin, heading).join(
                    heading,
                    heading.common_standard_type_code == outline.c.common_standard_type_code,
                )
            )
        ).all()
        by_code = {row.common_standard_type_code: row for _, row in rows}
        paths: dict[str, list[FoodCommonStandardType]] = {}
        for code in type_codes:
            path: list[FoodCommonStandardType] = []
            current = by_code.get(code)
            while current is not None and current not in path:
                path.append(current)
                parent = current.parent_common_standard_type_code
                current = None if parent is None else by_code.get(parent)
            path.reverse()
            paths[code] = path
        return paths
