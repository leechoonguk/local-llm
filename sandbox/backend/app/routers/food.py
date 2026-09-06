# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from fastapi import APIRouter

from app.core.settings import settings
from app.dependencies.auth import CurrentUserDep
from app.dependencies.query import ExactFilterQuery, LimitQuery, OffsetQuery, TextFilterQuery
from app.dependencies.services import FoodRawMaterialServiceDep
from app.schemas.food.raw_material import (
    FoodRawMaterialFacets,
    FoodRawMaterialFilter,
    FoodRawMaterialReadResponse,
    to_read_list,
)
from app.schemas.page import Page


# ============================================================
# Router
# ============================================================

# Read-only, on purpose. Every `food_*` table is a ledger a nightly sync fills
# from the provider (rule://backend-batch); a row written by hand here would be
# compared against the provider's record on the next pass and overwritten. So
# there is no POST, PATCH or DELETE, and `check-backend-domain` refuses one on
# a ledger domain rather than requiring it. No GET-by-id either: the screen is a
# grid over the page, every column is a grid column, and a route with no caller
# is refused by `check-frontend-contract`.
router = APIRouter(
    prefix="/food",
    tags=["food"],
    responses={404: {"description": "Not found"}},
)


@router.get("/raw-material/")
async def list_raw_materials(
    food_raw_material_service: FoodRawMaterialServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
    raw_material_code: TextFilterQuery = None,
    representative_raw_material_name: TextFilterQuery = None,
    raw_material_alias: TextFilterQuery = None,
    raw_material_large_class: ExactFilterQuery = None,
    raw_material_medium_class: ExactFilterQuery = None,
    raw_material_status_code_name: ExactFilterQuery = None,
) -> Page[FoodRawMaterialReadResponse]:
    filters = FoodRawMaterialFilter(
        raw_material_code=raw_material_code,
        representative_raw_material_name=representative_raw_material_name,
        raw_material_alias=raw_material_alias,
        raw_material_large_class=raw_material_large_class,
        raw_material_medium_class=raw_material_medium_class,
        raw_material_status_code_name=raw_material_status_code_name,
    )
    return Page(
        items=to_read_list(
            await food_raw_material_service.list_raw_materials(offset, limit, filters)
        ),
        total=await food_raw_material_service.count_raw_materials(filters),
    )


@router.get("/raw-material/facets")
async def list_raw_material_facets(
    food_raw_material_service: FoodRawMaterialServiceDep, current_user: CurrentUserDep
) -> FoodRawMaterialFacets:
    """The values the select filters offer - the ledger's own, read tonight not typed once."""
    return await food_raw_material_service.list_raw_material_facets()
