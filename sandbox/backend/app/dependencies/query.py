# ============================================================
# Imports
# ============================================================

from typing import Annotated

from fastapi import Query


# Pagination query params — Annotated aliases so routers never use inline
# Query() (FastAPI recommends Annotated type hints for DI). Defaults are set
# with `=` at the call site, not inside Annotated.


# ============================================================
# Constants
# ============================================================

#: The longest fragment a field filter accepts. It is the widest filterable
#: column (`user.email`, String(255)): a needle longer than the haystack can
#: never match, so a longer string is a client bug answered at the boundary
#: rather than a full scan that returns nothing.
TEXT_FILTER_MAX_LENGTH = 255


# ============================================================
# Dependencies
# ============================================================

OffsetQuery = Annotated[int, Query(ge=0)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]

#: A contains-filter on one text column, named after the column it filters
#: (`username=ali`). One alias serves every such parameter: the shape is the
#: same, and the column is the parameter's name — a caller reads which field it
#: narrows instead of guessing which columns a combined `search` covers.
#: `min_length=1` because an empty string is the absence of a filter spelled a
#: second way — the caller omits the parameter instead.
TextFilterQuery = Annotated[str | None, Query(min_length=1, max_length=TEXT_FILTER_MAX_LENGTH)]

#: An equals-filter on one closed-vocabulary column (`raw_material_large_class=식물`).
#: The wire shape is the text filter's - one string, never empty - and the
#: difference is the match: a value chosen from a list of the column's own values
#: matches whole, because `ilike '%식물%'` would also return `식물성유지`, which
#: the reader did not pick. The list the value came from is the list endpoint's
#: sibling `facets` route, so the caller never types one of these.
ExactFilterQuery = Annotated[str | None, Query(min_length=1, max_length=TEXT_FILTER_MAX_LENGTH)]
