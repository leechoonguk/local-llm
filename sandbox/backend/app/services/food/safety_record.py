# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from html import unescape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import LedgerStage, scan_table
from app.models.food import ledger_import_food_label as ledger_import
from app.models.food import safety_record as record_model
from app.models.food.ledger_collection_inspection import FoodLedgerCollectionInspection
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.models.food.ledger_inspection_failure import FoodLedgerInspectionFailure
from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.models.food.ledger_recall import FoodLedgerRecall
from app.models.food.safety_record import FoodSafetyRecord
from app.repositories.food.safety_record import FoodSafetyRecordRepository
from app.schemas.food.item_report import FoodSafetyRecordFacets, FoodSafetyRecordFilter
from app.services.food.item_report_declaration import PRODUCT_KEY, PRODUCT_PREFIX, digest


# ============================================================
# Constants
# ============================================================

# Two of the three feeds are small - 377 and 575 rows over the whole of each.
# The third is not: `food_ledger_collection_inspection` holds 2,045,467 rows and
# **all** of them are read, so this rebuild walks about 2,046 pages. Keeping only
# the 부적합 was the first shape, and it made a product never sampled and a
# product sampled twelve times and clean read the same on a screen.
PAGE_SIZE = 1000

# 검사부적합 publishes only failures, so its rows carry this verdict rather than
# read one: the table is narrowed by `judgment`, and a kind that sat outside
# that vocabulary would vanish from every 부적합 reading.
FAILED_JUDGMENT = "부적합"

# The portal's verdicts, read into the three codes a screen switches on.
# Measured over the whole 수거검사 feed: 적합 1,396,831, blank 431,947,
# 상기와같음 111,522, 검토중 96,305, 부적합 8,862. A blank is not yet published
# and 상기와같음 means "as above", where what is above is already published - so
# the first is pending and the second is a pass.
JUDGMENT_CODE_OF = {
    "부적합": record_model.JUDGMENT_FAILED,
    "적합": record_model.JUDGMENT_PASSED,
    "상기와같음": record_model.JUDGMENT_PASSED,
    "검토중": record_model.JUDGMENT_PENDING,
}

# What each ledger is read by and read for.
RECALL_KEY = ("recall_disuse_seq",)
RECALL_COLUMNS = (
    "item_report_no",
    "product_name",
    "business_name",
    "product_type_name",
    "manufactured_text",
    "recall_reason",
    "recall_method",
    "recall_grade",
    "registered_at",
)
INSPECTION_KEY = ("disposal_seq", "test_item_name", "standard_text")
INSPECTION_COLUMNS = (
    "item_report_no",
    "product_name",
    "business_name",
    "product_type_name",
    "manufactured_text",
    "test_result_text",
    "institution_name",
    "registered_on",
)
COLLECTION_KEY = ("record_digest",)
COLLECTION_COLUMNS = (
    "item_report_no",
    "product_name",
    "business_name",
    "collected_on",
    "judgment",
    "institution_name",
    "plan_title",
)

# The two registries an event's 품목제조보고번호 can belong to, in the vocabulary
# `food_item_report` owns - restated here because a derivation reads its own
# model module and the ledgers, never another derived table's.
DOMESTIC_KIND = "domestic"
LIVESTOCK_KIND = "livestock"
HEALTH_FUNCTIONAL_KIND = "health_functional"

# The registries that number their reports, and the kind a number in each one
# belongs to - the same tuple `barcode` and `nutrition` carry, and
# `check-backend-relations` compares the three against each other.
REGISTRIES = (
    (FoodLedgerItemReport, DOMESTIC_KIND),
    (FoodLedgerLivestockItemReportRawMaterial, LIVESTOCK_KIND),
    (FoodLedgerHealthFunctionalItemReport, HEALTH_FUNCTIONAL_KIND),
)

# The registry that numbers nothing, and how its records reach it instead:
# 수입식품 has no 품목제조보고번호 - the portal keys an import by the 수입신고
# (one declaration of one product, on one lot), and hangs a recall on that.
# Measured 2026-09-20 on impfood.mfds.go.kr: (주)태양무역 목이버섯 had six
# declarations and the 잔류농약 recall sat on exactly one, whose 소비기한
# starts on the recall's 제조일자. So an import record resolves by
# `(수입업체, 제조일자)` against the declaration ledger (`_lots`), never by
# number, which is why this registry is declared rather than listed above.
UNRESOLVED_REGISTRIES = {"FoodLedgerImportFoodLabel": "번호가 아니라 (수입업체, 로트일자)로 붙는다"}

IMPORT_KIND = "import"

# The columns the lot index reads off the declaration ledger: the product key
# `item_report_declaration` digests, plus the two that name a lot.
LOT_COLUMNS = (*PRODUCT_KEY, "expiry_from")

# A lot date out of 제조일자 as the feeds print it: "(포장일자) 2026.5.26",
# "2026. 7. 23.(포장일자)", "(제조일자)2026-07-23". One date, year first. A
# range ("2025-08-04~2026-07-08") names many lots and is read as none: 46 of 80
# unmapped recalls print no single date (2026-09-20), and an event put on a lot
# the feed never named would be a guess in a column a screen joins on.
_LOT_DATE = re.compile(r"(20\d\d)\D{0,3}(\d{1,2})\D{0,3}(\d{1,2})")

# Whitespace is not part of a name: the same importer declares "냉동 흰다리새우살"
# and "냉동흰다리새우살" (2026-09-20), and the recall spells it one of the two ways.
_SPACE = re.compile(r"\s+")

# `(수입업체, 로트일자)` → the products declared on that lot, as (digest, name).
Lots = dict[tuple[str, str], set[tuple[str, str]]]

# The digest's prefix per feed, so a key says which event it numbers on sight.
RECALL_PREFIX = "R"
INSPECTION_PREFIX = "F"
COLLECTION_PREFIX = "C"

# A date out of whatever the feed wrote it as: I0490 stamps a timestamp
# ("2026-09-14 17:19:13.501282"), I2620 dots a date ("2026.03.11"). Everything
# that is not a digit goes, and the first eight digits are the day; a string
# with fewer is not a date and is dropped.
_DIGITS = re.compile(r"\D")
DATE_DIGITS = 8


# ============================================================
# Classes
# ============================================================


class FoodSafetyRecordService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.record_repository = FoodSafetyRecordRepository(session)

    async def list_safety_records(
        self,
        offset: int,
        limit: int,
        filters: FoodSafetyRecordFilter | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> Sequence[FoodSafetyRecord]:
        """One page of published events, newest first unless the reader sorted it."""
        return await self.record_repository.list(offset, limit, filters, sort, order)

    async def count_safety_records(self, filters: FoodSafetyRecordFilter | None = None) -> int:
        """How many events that narrowing holds."""
        return await self.record_repository.count(filters)

    async def list_safety_record_facets(self) -> FoodSafetyRecordFacets:
        """The options the three selects offer, read off the table now."""
        # Validated rather than constructed: the two vocabularies are the
        # table's own words and the schema's `Literal`s at once, and a value
        # the table holds that the contract does not is a contract change
        # that should fail here, not read as a free string on a screen.
        return FoodSafetyRecordFacets.model_validate(
            {
                "record_kind": await self.record_repository.distinct_values(
                    FoodSafetyRecord.record_kind
                ),
                "judgment_code": await self.record_repository.distinct_values(
                    FoodSafetyRecord.judgment_code
                ),
                "report_kind": await self.record_repository.distinct_values(
                    FoodSafetyRecord.report_kind
                ),
                "record_year": await self.record_repository.distinct_years(),
            }
        )

    async def list_records(
        self, report_kind: str, item_report_no: str, offset: int = 0, limit: int = 100
    ) -> Sequence[FoodSafetyRecord]:
        """One page of a product's events, newest first."""
        return await self.record_repository.list_by_report(
            report_kind, item_report_no, offset, limit
        )

    async def summarise_records(
        self, report_kind: str, item_report_no: str
    ) -> tuple[int, int, str | None]:
        """What the product's section header states before a reader reads a row."""
        return await self.record_repository.summarise_by_report(report_kind, item_report_no)

    async def summarise_lots(
        self, report_kind: str, item_report_no: str, lot_dates: Sequence[str]
    ) -> dict[str, tuple[int, int, str | None]]:
        """What each declaration on the page carries - the badge beside a 수입신고."""
        return await self.record_repository.summarise_by_lots(
            report_kind, item_report_no, lot_dates
        )

    async def count_records(self, report_kind: str, item_report_no: str) -> int:
        """How many events the product carries - 0 for most products, which is the truth.

        948 events over both feeds (2026-09-14) against 1.9M products: an empty
        list here is the normal answer and says nothing was published, not that
        nothing was looked for.
        """
        return await self.record_repository.count_by_report(report_kind, item_report_no)

    async def rebuild_safety_record(self, synced_by: str) -> int:
        """Write `food_safety_record` off the three hazard ledgers; return its rows.

        One row per published event, whichever feed published it, numbered by
        the digest of that feed's own key columns. The product is attached by
        looking the 품목제조보고번호 up in `food_item_report`: it is in I1250 or
        in C006, and a number in neither keeps its number and no kind.

        Read off the live ledgers in keyed pages, staged, and written over whole
        in one short transaction (`LedgerStage.replace`, no floor: each ledger's
        own floor already vouched for its rows).
        """
        stage = LedgerStage(
            self.session,
            FoodSafetyRecord,
            record_model.NATURAL_KEY,
            record_model.SYNCED_COLUMNS,
        )
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                registry = await self._registry()
                lots = await self._lots()
                async for page in scan_table(
                    self.session, FoodLedgerRecall, RECALL_KEY, RECALL_COLUMNS, PAGE_SIZE
                ):
                    await stage.add([_readable(_recall(record, registry, lots)) for record in page])
                async for page in scan_table(
                    self.session,
                    FoodLedgerInspectionFailure,
                    INSPECTION_KEY,
                    INSPECTION_COLUMNS,
                    PAGE_SIZE,
                ):
                    await stage.add(
                        [_readable(_inspection(record, registry, lots)) for record in page]
                    )
                async for page in scan_table(
                    self.session,
                    FoodLedgerCollectionInspection,
                    COLLECTION_KEY,
                    COLLECTION_COLUMNS,
                    PAGE_SIZE,
                ):
                    await stage.add([_readable(_collection(record, registry)) for record in page])
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()

    async def _registry(self) -> dict[str, str]:
        """Which registry each reported number belongs to - the lookup the kind comes from.

        Read off the report ledgers rather than `food_item_report`: a
        derivation is a function of the ledgers, and one that reads another
        derived table would depend on the order `DERIVATIONS` writes them in
        (rule://backend-ledger). The answer is the same - that table is these
        ledgers - and a number belongs to one of them, because the registries
        number their reports in separate spaces (measured: no C006 number is in
        I1250, and no I0030 number is in either).

        **Every registry that numbers its reports, or the ones left out simply
        do not resolve.** 건강기능식품 (I0030) was missing here while
        `food_item_report` derived it, and 18,536 records of 5,648 numbers -
        every 수거검사 of a 건강기능식품 - carried their number with no kind, so
        the read layer dropped them as naming no product we hold. The fourth
        registry, 수입식품, is absent on purpose: its numbers are digests this
        codebase mints (`_import_product`), not 품목제조보고번호, so no
        published record can carry one.

        1,686,325 numbers at two short strings each. Held in memory because
        every one of the two million records asks the same question.
        """
        registry: dict[str, str] = {}
        for model, kind in REGISTRIES:
            rows = await self.session.execute(select(model.item_report_no))
            registry.update({number: kind for (number,) in rows.all()})
        return registry

    async def _lots(self) -> Lots:
        """Every import lot by importer and day - the lookup an import event resolves through.

        `(수입업체, 소비기한 시작일)` → the products declared on that lot, each
        as the digest `item_report_declaration` numbers it by and the name it
        was declared under. Read off the declaration ledger, not off
        `food_item_report_declaration`, for the reason `_registry` gives;
        the digest is the same function over the same columns, so the number
        this writes is the number that table holds.

        A set per key rather than one product: the same importer declares
        several products on one day (다이아몬드새우, 2025-12-26: four), and
        which one an event names is settled by `_import_product`, not here.
        """
        lots: dict[tuple[str, str], set[tuple[str, str]]] = {}
        rows = await self.session.execute(
            select(*(getattr(FoodLedgerImportFoodLabel, name) for name in LOT_COLUMNS)).where(
                FoodLedgerImportFoodLabel.expiry_from != "",
                # The same boundary `item_report` derives products under: a
                # crossing of a commodity or a package is not a product, so an
                # event on one resolves to nothing rather than to a digest no
                # product row carries.
                FoodLedgerImportFoodLabel.declaration_kind.in_(
                    ledger_import.PRODUCT_DECLARATION_KINDS
                ),
            )
        )
        for row in rows.mappings():
            record = dict(row)
            key = (_flat(record["importer_name"]), str(record["expiry_from"]))
            lots.setdefault(key, set()).add(
                (digest(PRODUCT_PREFIX, record, PRODUCT_KEY), _flat(record["product_name"]))
            )
        return lots


# ============================================================
# Functions
# ============================================================


def _readable(row: dict[str, object]) -> dict[str, object]:
    """One mapped row with every text value unescaped - see `_unescaped`."""
    return {key: _unescaped(value) for key, value in row.items()}


def _unescaped(value: object) -> object:
    """The portal's text with its HTML entities resolved.

    식품안전나라 escapes for a web page and the ledger keeps what the wire said,
    so a table drawn from it printed `2026년 국내 주류 수거&middot;검사`. Measured
    over the whole record set: 27,160 reasons, 2,862 product names and 2,737
    business names carry one - `&#39;` 16,468, `&middot;` 8,988, `&rsquo;`
    1,331, `&amp;` 327, `&lsquo;` 37, `&quot;` 9. The derivation is where it is
    undone, because the ledger is the feed's copy and this table is what a
    reader reads.
    """
    return unescape(value) if isinstance(value, str) else value


def _recorded_on(text: object) -> str | None:
    """The day a record is dated, out of each feed's own spelling of it.

    I0490 stamps a timestamp, I2620 dots a date, I0460 writes 수거일자 as eight
    digits - everything that is not a digit goes, and the first eight are the day.
    """
    digits = _DIGITS.sub("", str(text or ""))
    return digits[:DATE_DIGITS] if len(digits) >= DATE_DIGITS else None


def _recall(
    record: Mapping[str, object], registry: Mapping[str, str], lots: Lots
) -> dict[str, object]:
    """One 회수·판매중지 as a record - an action, so it carries no verdict."""
    report_kind, number, lot_date = _product(record, registry, lots)
    return {
        "record_key": digest(RECALL_PREFIX, record, RECALL_KEY),
        "record_kind": record_model.RECALL_KIND,
        "judgment": None,
        "judgment_code": None,
        "report_kind": report_kind,
        "item_report_no": number,
        "recorded_on": _recorded_on(record.get("registered_at")),
        "manufactured_text": record.get("manufactured_text"),
        "lot_date": lot_date,
        "reason": record.get("recall_reason"),
        "method": record.get("recall_method"),
        "grade": record.get("recall_grade"),
        "test_item_name": None,
        "standard_text": None,
        "test_result_text": None,
        "institution_name": None,
        "product_name": record.get("product_name"),
        "business_name": record.get("business_name"),
        "product_type_name": record.get("product_type_name"),
    }


def _inspection(
    record: Mapping[str, object], registry: Mapping[str, str], lots: Lots
) -> dict[str, object]:
    """One 검사부적합 as a record - the failed item, not the disposal.

    The feed publishes only failures, so the verdict is the same on every row
    and is written rather than read: a reader narrowing the table by 부적합
    must find this kind beside the 수거검사 that failed.
    """
    report_kind, number, lot_date = _product(record, registry, lots)
    return {
        "record_key": digest(INSPECTION_PREFIX, record, INSPECTION_KEY),
        "record_kind": record_model.INSPECTION_FAILURE_KIND,
        "judgment": FAILED_JUDGMENT,
        "judgment_code": record_model.JUDGMENT_FAILED,
        "report_kind": report_kind,
        "item_report_no": number,
        "recorded_on": _recorded_on(record.get("registered_on")),
        "manufactured_text": record.get("manufactured_text"),
        "lot_date": lot_date,
        "reason": None,
        "method": None,
        "grade": None,
        "test_item_name": record.get("test_item_name"),
        "standard_text": record.get("standard_text"),
        "test_result_text": record.get("test_result_text"),
        "institution_name": record.get("institution_name"),
        "product_name": record.get("product_name"),
        "business_name": record.get("business_name"),
        "product_type_name": record.get("product_type_name"),
    }


def _collection(record: Mapping[str, object], registry: Mapping[str, str]) -> dict[str, object]:
    """One 수거검사 as a record - the specimen and what it was judged.

    Every verdict, not only 부적합: a product sampled twelve times and clean is
    a different fact from one never sampled, and only these rows can tell them
    apart. The feed names no 검사항목, no 기준 and no 측정치, so those three
    columns stay NULL; the plan it was collected under ("민원관련 수거검사") is
    the nearest thing to a reason it states, so it is where `reason` comes from.
    """
    number = _key_text(record.get("item_report_no"))
    judgment = _key_text(record.get("judgment"))
    return {
        "record_key": digest(COLLECTION_PREFIX, record, COLLECTION_KEY),
        "record_kind": record_model.COLLECTION_INSPECTION_KIND,
        "judgment": judgment,
        # A verdict the portal has not published is pending, not unknown: the
        # blank is 21.1 % of the feed and it means the specimen is still out.
        "judgment_code": JUDGMENT_CODE_OF.get(judgment or "", record_model.JUDGMENT_PENDING),
        "report_kind": registry.get(number or ""),
        "item_report_no": number,
        "recorded_on": _recorded_on(record.get("collected_on")),
        "manufactured_text": None,
        "lot_date": None,
        "reason": record.get("plan_title"),
        "method": None,
        "grade": None,
        "test_item_name": None,
        "standard_text": None,
        "test_result_text": None,
        "institution_name": record.get("institution_name"),
        "product_name": record.get("product_name"),
        "business_name": record.get("business_name"),
        "product_type_name": None,
    }


def _key_text(value: object) -> str | None:
    """A number the feed left empty is absent, not the empty string."""
    text = str(value or "").strip()
    return text or None


def _product(
    record: Mapping[str, object], registry: Mapping[str, str], lots: Lots
) -> tuple[str | None, str | None, str | None]:
    """Which product an event is about: its registry, its number and its lot.

    By number where the feed printed one - it is in one of the three numbered
    registries or in none. Where it printed none, the event may still be an
    import, and an import is reached the way the portal reaches it: the
    business is the importer and 제조일자 is the lot the declaration was made
    on. A number that is printed but resolves nowhere stays as printed, kind
    NULL, and is not tried as an import - it named a registry, just not one held.
    """
    number = _key_text(record.get("item_report_no"))
    lot_date = _lot_date(record.get("manufactured_text"))
    if number is not None:
        return registry.get(number), number, lot_date
    if lot_date is None:
        return None, None, None
    product = _import_product(
        lots, record.get("business_name"), lot_date, record.get("product_name")
    )
    return (IMPORT_KIND, product, lot_date) if product is not None else (None, None, lot_date)


def _import_product(
    lots: Lots, business: object, lot_date: str, product_name: object
) -> str | None:
    """The one import product an event on this importer's lot names, or None.

    The lot narrows it to what that importer declared on that day; the name
    picks among them. Measured 2026-09-20 over every dated, unnumbered recall:
    13 have exactly one product under the name, 1 has one product on the lot
    however it is named ("목이버섯" against "목이버섯(1kg*10)"), 1 is two
    products that differ by a space and stays unresolved. Nothing is guessed
    past those two rules.
    """
    candidates = lots.get((_flat(business), lot_date))
    if not candidates:
        return None
    name = _flat(product_name)
    by_name = {number for number, declared in candidates if declared == name}
    if len(by_name) == 1:
        return by_name.pop()
    by_lot = {number for number, _ in candidates}
    return by_lot.pop() if len(by_lot) == 1 else None


def _lot_date(text: object) -> str | None:
    """`20260526` out of 제조일자 as printed, or None where it prints no single date."""
    dates = _LOT_DATE.findall(str(text or ""))
    if len(dates) != 1:
        return None
    year, month, day = dates[0]
    return f"{year}{int(month):02d}{int(day):02d}"


def _flat(value: object) -> str:
    """A name with its whitespace removed, so two spellings of one name compare equal."""
    return _SPACE.sub("", str(value or ""))
