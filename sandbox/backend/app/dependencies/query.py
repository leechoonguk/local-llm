# ============================================================
# Imports
# ============================================================

from typing import Annotated, Literal

from fastapi import Query

from app.schemas.food.business import BusinessStatus
from app.schemas.food.item_report import JudgmentCode, RecordKind, ReportKind
from app.schemas.food.raw_material import UseFlag


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

#: One end of a range, not a value to match: the repository compares it with
#: `>=` or `<=` rather than by equality or by fragment. The publisher's dates
#: are fixed-width strings (`20260914`), so the bound is one of those.
BoundFilterQuery = Annotated[str | None, Query(min_length=1, max_length=TEXT_FILTER_MAX_LENGTH)]

#: An equals-filter whose vocabulary the schema already closes (`report_kind=food`):
#: the Literal is the validator, so a value outside it is a 422 at the boundary
#: and the filter object never sees a string it cannot switch on.
ReportKindQuery = Annotated[ReportKind | None, Query()]

#: Which kind of thing an authority published - the record table's own literal.
RecordKindQuery = Annotated[RecordKind | None, Query()]

#: Our reading of 판정결과 - the portal's own word is data and is not a filter.
JudgmentCodeQuery = Annotated[JudgmentCode | None, Query()]

#: Whether a page is limited to records that name a product this database holds.
#: On by default: 1,553,789 rows of `food_safety_record` name none, and a screen
#: about products cannot draw them. `mapped=false` asks for them anyway.
MappedQuery = Annotated[bool, Query()]

#: The same shape for the raw material registry's use flag (`use_yn=N`: retired codes).
UseFlagQuery = Annotated[UseFlag | None, Query()]

#: Which ledger a business row came from - live master or closure feed - the pair the schema closes.
BusinessStatusQuery = Annotated[BusinessStatus | None, Query()]

# A yes/no narrowing that is not a column: "only the products something was
# published about". Absent and false both leave the page alone, so a screen
# sends it only when the box is ticked.
FlagQuery = Annotated[bool | None, Query()]

#: Which way a sorted list runs. One closed pair, so a typo is a 422 at the
#: boundary and the repository never sees a word it cannot switch on.
OrderQuery = Annotated[Literal["asc", "desc"], Query()]

#: Which column a list is sorted by - one alias per list endpoint, each a
#: Literal of the columns the screen's grid can sort. Closed on purpose: a
#: `sort` parameter open to any string would be one `getattr` away from a
#: 500, and the grid's header is the only caller. `None` is the endpoint's
#: own default order, the one it paged by before sorting existed.
UserSortQuery = Annotated[Literal["username", "email", "created_at"] | None, Query()]
BatchSortQuery = Annotated[Literal["code", "cron", "enabled", "created_at"] | None, Query()]
IntegrationSortQuery = Annotated[
    Literal["code", "display_name", "base_url", "enabled"] | None, Query()
]
FoodItemReportSortQuery = Annotated[
    Literal[
        "report_kind",
        "item_report_no",
        "product_name",
        "product_type_name",
        "business_name",
        "maker_name",
        "origin_country",
        "product_name_en",
        "license_no",
        "report_date",
        "industry_name",
        "shelf_life",
        "product_form",
        "packaging_material",
        "usage_method",
        "purpose",
        "quality_maintenance_days",
        "production_ended",
        "high_calorie_low_nutrition",
        "child_favorite_certified_yn",
        "domestic_export_type",
        "source_updated_at",
    ]
    | None,
    Query(),
]

#: What the event grid may sort on - the columns an authority's action is read
#: by. Ordered on the server, because a page sorted in the browser is a page
#: sorted, not a collection.
FoodSafetyRecordSortQuery = Annotated[
    Literal[
        "recorded_on",
        "record_kind",
        "judgment",
        "report_kind",
        "item_report_no",
        "product_name",
        "business_name",
        "grade",
        "institution_name",
    ]
    | None,
    Query(),
]
FoodRawMaterialSortQuery = Annotated[
    Literal[
        "raw_material_code",
        "representative_raw_material_name",
        "raw_material_large_class",
        "raw_material_medium_class",
        "region_code_name",
        "process_code_name",
        "raw_material_status_code_name",
        "use_yn",
        "english_name",
        "scientific_name",
        "source_updated_at",
    ]
    | None,
    Query(),
]
FoodBusinessSortQuery = Annotated[
    Literal[
        "license_no",
        "business_name",
        "industry_name",
        "status",
        "district",
        "permit_date",
        "closed_date",
    ]
    | None,
    Query(),
]
