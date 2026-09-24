# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import AsyncIterable
from uuid import UUID

from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.core.exceptions import ServiceUnavailableError
from app.core.settings import settings
from app.dependencies.auth import CurrentUserDep
from app.dependencies.query import (
    BoundFilterQuery,
    BusinessStatusQuery,
    ExactFilterQuery,
    FoodBusinessSortQuery,
    FoodItemReportSortQuery,
    FoodRawMaterialSortQuery,
    FoodSafetyRecordSortQuery,
    JudgmentCodeQuery,
    LimitQuery,
    MappedQuery,
    OffsetQuery,
    OrderQuery,
    RecordKindQuery,
    ReportKindQuery,
    TextFilterQuery,
    UseFlagQuery,
)
from app.dependencies.services import (
    FoodBusinessServiceDep,
    FoodChatServiceDep,
    FoodItemReportDeclarationServiceDep,
    FoodItemReportServiceDep,
    FoodRawMaterialServiceDep,
    FoodSafetyRecordServiceDep,
)
from app.schemas.food import business as business_schema
from app.schemas.food import raw_material as raw_material_schema
from app.schemas.food.business import (
    FoodBusinessDetailReadResponse,
    FoodBusinessFacets,
    FoodBusinessFilter,
    FoodBusinessReadResponse,
)
from app.schemas.food.chat import (
    SERVICE_UNAVAILABLE_CODE,
    FoodChatAskRequest,
    FoodChatErrorEvent,
)
from app.schemas.food.item_report import (
    FoodItemReportDeclarationReadResponse,
    FoodItemReportDetailReadResponse,
    FoodItemReportFacets,
    FoodItemReportFilter,
    FoodItemReportLabelAllergenReadResponse,
    FoodItemReportLabelBase,
    FoodItemReportLabelCautionReadResponse,
    FoodItemReportLabelPackagingReadResponse,
    FoodItemReportLabelReadResponse,
    FoodItemReportLabelsReadResponse,
    FoodItemReportReadResponse,
    FoodItemReportStandardsReadResponse,
    FoodItemReportTypeStandardsReadResponse,
    FoodSafetyRecordFacets,
    FoodSafetyRecordFilter,
    FoodSafetyRecordReadResponse,
    to_read,
    to_read_list,
)
from app.schemas.food.raw_material import (
    FoodRawMaterialDetailReadResponse,
    FoodRawMaterialFacets,
    FoodRawMaterialFilter,
    FoodRawMaterialReadResponse,
)
from app.schemas.page import Page


# ============================================================
# Router
# ============================================================

# Read-only, on purpose. Every `food_*` table the API serves is derived - the
# derive job rebuilds it whole off the ledgers every night (rule://backend-ledger)
# - so a row written by hand here would be gone by morning. There is no POST,
# PATCH or DELETE, and `check-backend-domain` refuses one on a derived table
# rather than requiring it. The ledgers themselves have no route at all.
router = APIRouter(
    prefix="/food",
    tags=["food"],
    responses={404: {"description": "Not found"}},
)


@router.get("/item-report/")
async def list_item_reports(
    food_item_report_service: FoodItemReportServiceDep,
    food_safety_record_service: FoodSafetyRecordServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
    report_kind: ReportKindQuery = None,
    item_report_no: TextFilterQuery = None,
    license_no: TextFilterQuery = None,
    business_name: TextFilterQuery = None,
    product_name: TextFilterQuery = None,
    product_type_name: ExactFilterQuery = None,
    sort: FoodItemReportSortQuery = None,
    order: OrderQuery = "asc",
) -> Page[FoodItemReportReadResponse]:
    filters = FoodItemReportFilter(
        report_kind=report_kind,
        item_report_no=item_report_no,
        license_no=license_no,
        business_name=business_name,
        product_name=product_name,
        product_type_name=product_type_name,
    )
    item_reports = await food_item_report_service.list_item_reports(
        offset, limit, filters, sort, order
    )
    return Page(
        items=[to_read(item_report) for item_report in item_reports],
        total=await food_item_report_service.count_item_reports(filters),
    )


@router.get("/safety-record/")
async def list_safety_records(
    food_safety_record_service: FoodSafetyRecordServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
    record_kind: RecordKindQuery = None,
    judgment_code: JudgmentCodeQuery = None,
    mapped: MappedQuery = True,
    report_kind: ReportKindQuery = None,
    record_year: ExactFilterQuery = None,
    recorded_on_from: BoundFilterQuery = None,
    recorded_on_to: BoundFilterQuery = None,
    item_report_no: TextFilterQuery = None,
    product_name: TextFilterQuery = None,
    business_name: TextFilterQuery = None,
    sort: FoodSafetyRecordSortQuery = None,
    order: OrderQuery = "asc",
) -> Page[FoodSafetyRecordReadResponse]:
    """What authorities inspected and did, newest first - across every product.

    A record is not the owner's declaration but an authority's finding or
    action, and it is read the way such a thing is read: by date, kind and
    verdict, over everything, rather than one product at a time.

    Records naming no product this database holds are out of the page unless
    `mapped=false` asks for them: 1,553,789 of them say nothing a screen about
    products could draw.
    """
    filters = FoodSafetyRecordFilter(
        record_kind=record_kind,
        judgment_code=judgment_code,
        mapped=mapped,
        report_kind=report_kind,
        record_year=record_year,
        recorded_on_from=recorded_on_from,
        recorded_on_to=recorded_on_to,
        item_report_no=item_report_no,
        product_name=product_name,
        business_name=business_name,
    )
    return Page(
        items=[
            FoodSafetyRecordReadResponse.model_validate(event)
            for event in await food_safety_record_service.list_safety_records(
                offset, limit, filters, sort, order
            )
        ],
        total=await food_safety_record_service.count_safety_records(filters),
    )


@router.get("/safety-record/facets")
async def list_safety_record_facets(
    food_safety_record_service: FoodSafetyRecordServiceDep, current_user: CurrentUserDep
) -> FoodSafetyRecordFacets:
    """The values the 종류·구분·연도 selects offer - the table's own, read now."""
    return await food_safety_record_service.list_safety_record_facets()


@router.get("/item-report/facets")
async def list_item_report_facets(
    food_item_report_service: FoodItemReportServiceDep, current_user: CurrentUserDep
) -> FoodItemReportFacets:
    """The values the 식품유형 select offers - the table's own, read now, not typed once."""
    return await food_item_report_service.list_item_report_facets()


@router.get("/item-report/{food_item_report_id}")
async def get_item_report(
    food_item_report_id: UUID,
    food_item_report_service: FoodItemReportServiceDep,
    food_item_report_declaration_service: FoodItemReportDeclarationServiceDep,
    food_safety_record_service: FoodSafetyRecordServiceDep,
    current_user: CurrentUserDep,
) -> FoodItemReportDetailReadResponse:
    """The report with its label's ingredients and its nutrition."""
    item_report = await food_item_report_service.get_item_report(food_item_report_id)
    key = (item_report.report_kind, item_report.item_report_no)
    declarations = await food_item_report_declaration_service.count_declarations(*key)
    records, failed, latest = await food_safety_record_service.summarise_records(*key)
    return FoodItemReportDetailReadResponse.model_validate(
        {
            **to_read(item_report).model_dump(),
            "ingredients": item_report.ingredients,
            "nutritions": item_report.nutritions,
            "declaration_count": declarations,
            "record_count": records,
            "failed_record_count": failed,
            "last_recorded_on": latest,
        }
    )


@router.get("/item-report/{food_item_report_id}/declarations")
async def list_item_report_declarations(
    food_item_report_id: UUID,
    food_item_report_service: FoodItemReportServiceDep,
    food_item_report_declaration_service: FoodItemReportDeclarationServiceDep,
    food_safety_record_service: FoodSafetyRecordServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> Page[FoodItemReportDeclarationReadResponse]:
    """Every declaration of the product, newest 처리일자 first, with what was published on each.

    Three services, because the three tables are three derivations: the report
    says which product this is, the declaration service answers for that pair,
    and the record service says which of the page's lots an authority acted
    on - the portal hangs a recall on one 수입신고 of a product's many, and this
    is where a reader sees which.
    """
    item_report = await food_item_report_service.get_item_report(food_item_report_id)
    key = (item_report.report_kind, item_report.item_report_no)
    declarations = await food_item_report_declaration_service.list_declarations(*key, offset, limit)
    lots = await food_safety_record_service.summarise_lots(
        *key, [d.expiry_from for d in declarations if d.expiry_from]
    )
    return Page(
        items=[
            FoodItemReportDeclarationReadResponse.model_validate(declaration).model_copy(
                update=dict(
                    zip(
                        ("record_count", "failed_record_count", "recall_grade"),
                        lots.get(declaration.expiry_from or "", (0, 0, None)),
                        strict=True,
                    )
                )
            )
            for declaration in declarations
        ],
        total=await food_item_report_declaration_service.count_declarations(*key),
    )


@router.get("/item-report/{food_item_report_id}/safety-records")
async def list_safety_records_of_item_report(
    food_item_report_id: UUID,
    food_item_report_service: FoodItemReportServiceDep,
    food_safety_record_service: FoodSafetyRecordServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> Page[FoodSafetyRecordReadResponse]:
    """What was inspected and what was done about the product, newest first."""
    item_report = await food_item_report_service.get_item_report(food_item_report_id)
    key = (item_report.report_kind, item_report.item_report_no)
    return Page(
        items=[
            FoodSafetyRecordReadResponse.model_validate(event)
            for event in await food_safety_record_service.list_records(*key, offset, limit)
        ],
        total=await food_safety_record_service.count_records(*key),
    )


@router.get("/item-report/{food_item_report_id}/standards")
async def get_item_report_standards(
    food_item_report_id: UUID,
    food_item_report_service: FoodItemReportServiceDep,
    current_user: CurrentUserDep,
) -> FoodItemReportStandardsReadResponse:
    """Per type the report names: its 제5 clauses, and the 제2 clauses it inherits."""
    types = await food_item_report_service.get_item_report_standards(food_item_report_id)
    return FoodItemReportStandardsReadResponse(
        types=[FoodItemReportTypeStandardsReadResponse.model_validate(entry) for entry in types]
    )


@router.get("/item-report/{food_item_report_id}/labels")
async def get_item_report_labels(
    food_item_report_id: UUID,
    food_item_report_service: FoodItemReportServiceDep,
    current_user: CurrentUserDep,
) -> FoodItemReportLabelsReadResponse:
    """The 푸드QR 라벨 printed under this report: its 표시사항, its panel, its allergens."""
    labels = await food_item_report_service.get_item_report_labels(food_item_report_id)
    return FoodItemReportLabelsReadResponse(
        labels=[
            FoodItemReportLabelReadResponse(
                **FoodItemReportLabelBase.model_validate(entry.label).model_dump(),
                allergens=[
                    FoodItemReportLabelAllergenReadResponse.model_validate(row)
                    for row in entry.allergens
                ],
                cautions=[
                    FoodItemReportLabelCautionReadResponse.model_validate(row)
                    for row in entry.cautions
                ],
                packagings=[
                    FoodItemReportLabelPackagingReadResponse.model_validate(row)
                    for row in entry.packagings
                ],
            )
            for entry in labels
        ]
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
    use_yn: UseFlagQuery = None,
    sort: FoodRawMaterialSortQuery = None,
    order: OrderQuery = "asc",
) -> Page[FoodRawMaterialReadResponse]:
    filters = FoodRawMaterialFilter(
        raw_material_code=raw_material_code,
        representative_raw_material_name=representative_raw_material_name,
        raw_material_alias=raw_material_alias,
        raw_material_large_class=raw_material_large_class,
        raw_material_medium_class=raw_material_medium_class,
        raw_material_status_code_name=raw_material_status_code_name,
        use_yn=use_yn,
    )
    return Page(
        items=raw_material_schema.to_read_list(
            await food_raw_material_service.list_raw_materials(offset, limit, filters, sort, order)
        ),
        total=await food_raw_material_service.count_raw_materials(filters),
    )


@router.get("/raw-material/facets")
async def list_raw_material_facets(
    food_raw_material_service: FoodRawMaterialServiceDep, current_user: CurrentUserDep
) -> FoodRawMaterialFacets:
    """The values the select filters offer - the table's own, read now, not typed once."""
    return await food_raw_material_service.list_raw_material_facets()


@router.get("/raw-material/{food_raw_material_id}")
async def get_raw_material(
    food_raw_material_id: UUID,
    food_raw_material_service: FoodRawMaterialServiceDep,
    current_user: CurrentUserDep,
) -> FoodRawMaterialDetailReadResponse:
    """The material with its composition's siblings - every code of the same base."""
    raw_material = await food_raw_material_service.get_raw_material(food_raw_material_id)
    return FoodRawMaterialDetailReadResponse.model_validate(raw_material)


@router.get("/raw-material/{food_raw_material_id}/item-reports")
async def list_raw_material_item_reports(
    food_raw_material_id: UUID,
    food_item_report_service: FoodItemReportServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> Page[FoodItemReportReadResponse]:
    """The products whose label names this material, as the derive job resolved the names."""
    return Page(
        items=to_read_list(
            await food_item_report_service.list_item_reports_by_raw_material(
                food_raw_material_id, offset, limit
            )
        ),
        total=await food_item_report_service.count_item_reports_by_raw_material(
            food_raw_material_id
        ),
    )


@router.get("/business/")
async def list_businesses(
    food_business_service: FoodBusinessServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
    business_name: TextFilterQuery = None,
    license_no: TextFilterQuery = None,
    district: TextFilterQuery = None,
    industry_name: ExactFilterQuery = None,
    status: BusinessStatusQuery = None,
    sort: FoodBusinessSortQuery = None,
    order: OrderQuery = "asc",
) -> Page[FoodBusinessReadResponse]:
    filters = FoodBusinessFilter(
        business_name=business_name,
        license_no=license_no,
        district=district,
        industry_name=industry_name,
        status=status,
    )
    return Page(
        items=business_schema.to_read_list(
            await food_business_service.list_businesses(offset, limit, filters, sort, order)
        ),
        total=await food_business_service.count_businesses(filters),
    )


@router.get("/business/facets")
async def list_business_facets(
    food_business_service: FoodBusinessServiceDep, current_user: CurrentUserDep
) -> FoodBusinessFacets:
    """The values the 업종 select offers - the table's own, read now, not typed once."""
    return await food_business_service.list_business_facets()


@router.get("/business/{food_business_id}")
async def get_business(
    food_business_id: UUID,
    food_business_service: FoodBusinessServiceDep,
    current_user: CurrentUserDep,
) -> FoodBusinessDetailReadResponse:
    """The business with the rows it shares a name or a site with - candidates, never one owner."""
    business = await food_business_service.get_business(food_business_id)
    return FoodBusinessDetailReadResponse(
        **business_schema.to_read(business).model_dump(),
        same_name=business_schema.to_read_list(
            await food_business_service.list_same_name(business)
        ),
        same_site=business_schema.to_read_list(
            await food_business_service.list_same_site(business)
        ),
    )


@router.post("/chat", response_class=EventSourceResponse)
async def ask_chat(
    data: FoodChatAskRequest,
    food_chat_service: FoodChatServiceDep,
    current_user: CurrentUserDep,
) -> AsyncIterable[ServerSentEvent]:
    """One turn of chat, streamed: many `token` events, then one `end` - or one `error`.

    POST rather than GET because the question is a body, and because the
    browser's own `EventSource` cannot carry a bearer token: the client reads
    the stream through the same authenticated transport as every other call
    (`lib/api/client.ts`).

    A failure mid-answer is an `error` event, not a dropped connection: the
    status line is long gone by then, so a stream that simply stops is
    indistinguishable from a lost network, and the screen would show half an
    answer as if it were the whole one.
    """
    pieces: list[str] = []
    try:
        async for token in food_chat_service.answer(data.message):
            pieces.append(token.text)
            yield ServerSentEvent(data=token, event="token")
    except ServiceUnavailableError:
        yield ServerSentEvent(data=FoodChatErrorEvent(code=SERVICE_UNAVAILABLE_CODE), event="error")
        return
    yield ServerSentEvent(data=food_chat_service.summarise(pieces), event="end")
