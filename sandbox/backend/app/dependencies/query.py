# ============================================================
# Imports
# ============================================================

from typing import Annotated

from fastapi import Query


# Pagination query params — Annotated aliases so routers never use inline
# Query() (FastAPI recommends Annotated type hints for DI). Defaults are set
# with `=` at the call site, not inside Annotated.


# ============================================================
# Dependencies
# ============================================================

OffsetQuery = Annotated[int, Query(ge=0)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
