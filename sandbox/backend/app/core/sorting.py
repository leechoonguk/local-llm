# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from typing import Any

from sqlalchemy import Select
from sqlalchemy.orm import InstrumentedAttribute


# ============================================================
# Functions
# ============================================================


def ordered(
    query: Select[Any],
    model: type[Any],
    sort: str | None,
    order: str,
    *default: InstrumentedAttribute[Any],
) -> Select[Any]:
    """Order a list query by the column the caller named, then by the endpoint's own order.

    The default order stays as a tiebreak, so a page cut through a run of equal
    values (every 사용 badge, every 2026-09-06 timestamp) lands on the same
    rows twice rather than on two overlapping sets. `sort` is one of a Literal
    the router closed, so `getattr` cannot miss.
    """
    if sort is None:
        return query.order_by(*default)
    column = getattr(model, sort)
    return query.order_by(column.desc() if order == "desc" else column.asc(), *default)
