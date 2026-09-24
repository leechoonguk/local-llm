# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.product_classification import FoodProductClassification


# ============================================================
# Classes
# ============================================================


class FoodProductClassificationRepository:
    """Reads over the derived classification tree. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_ancestor_paths(
        self, product_codes: Sequence[str]
    ) -> dict[str, list[FoodProductClassification]]:
        """Each node's path from its root down to itself, root first.

        The walk up `parent_product_code` is the one place in the food domain
        a join is spelled by column rather than along an edge, and it is here
        because it is recursive - an edge is one step, and a path is as many
        as the tree is deep (five, measured 2026-09-08). One recursive CTE
        for every code asked, so a report that names three types costs one
        query and not three.
        """
        if not product_codes:
            return {}
        node = FoodProductClassification
        seed = (
            select(node.product_code.label("origin"), node.product_code, node.parent_product_code)
            .where(node.product_code.in_(list(product_codes)))
            .cte("ancestry", recursive=True)
        )
        step = select(seed.c.origin, node.product_code, node.parent_product_code).join(
            seed, seed.c.parent_product_code == node.product_code
        )
        ancestry = seed.union_all(step)
        rows = (
            await self.session.execute(
                select(ancestry.c.origin, node).join(
                    node, node.product_code == ancestry.c.product_code
                )
            )
        ).all()
        by_code = {row.product_code: row for _, row in rows}
        paths: dict[str, list[FoodProductClassification]] = {}
        for code in product_codes:
            path: list[FoodProductClassification] = []
            current = by_code.get(code)
            while current is not None and current not in path:
                path.append(current)
                parent = current.parent_product_code
                current = None if parent is None else by_code.get(parent)
            path.reverse()
            paths[code] = path
        return paths
