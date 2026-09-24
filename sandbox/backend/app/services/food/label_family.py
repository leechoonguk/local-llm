# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import re
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import LedgerStage, scan_table
from app.core.printed_label import (
    keep_newest,
    printed_names,
    printed_parts,
    printed_section,
    split_list,
)
from app.models.food import label as label_model
from app.models.food import label_allergen as allergen_model
from app.models.food import label_caution as label_caution_model
from app.models.food import label_packaging as label_packaging_model
from app.models.food import ledger_health_functional_item_report as ledger_health_functional
from app.models.food import ledger_import_food_label, ledger_item_report
from app.models.food import ledger_import_food_label as ledger_import
from app.models.food import ledger_livestock_item_report_raw_material as ledger_livestock
from app.models.food.label import FoodLabel
from app.models.food.label_allergen import FoodLabelAllergen
from app.models.food.label_caution import FoodLabelCaution
from app.models.food.label_packaging import FoodLabelPackaging
from app.models.food.ledger_haccp_label import FoodLedgerHaccpLabel
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.models.food.ledger_qr_allergy import FoodLedgerQrAllergy
from app.models.food.ledger_qr_caution import FoodLedgerQrCaution
from app.models.food.ledger_qr_label import FoodLedgerQrLabel
from app.models.food.ledger_qr_manufacture import FoodLedgerQrManufacture
from app.models.food.ledger_qr_nutrition import FoodLedgerQrNutrition
from app.models.food.ledger_qr_packaging import FoodLedgerQrPackaging
from app.models.food.ledger_qr_raw_material import FoodLedgerQrRawMaterial
from app.models.food.ledger_qr_storage import FoodLedgerQrStorage
from app.services.food.item_report_declaration import (
    DECLARATION_KEY,
    PRODUCT_KEY,
    PRODUCT_PREFIX,
    digest,
)


# ============================================================
# Constants
# ============================================================

# **One paragraph, one pass.** `food_label` and its three children are one
# family of facts about one printed label, and until 2026-09-14 four derivations
# each walked the 1,055,682-row import ledger and parsed the same paragraph
# again - six scans of that ledger over the derive job, six parses of every
# label. They are written here instead: one scan, one parse, four tables, four
# stages committed in the same pass (rule://backend-ledger, "A Table Family Of
# One Paragraph Is One Derivation").

# Rows are staged in batches of this many; the two sources are 4,765 and 14,664
# labels (2026-09-13), so a rebuild is a handful of batches.
PAGE_SIZE = 1000

# The import ledger is read in key order by this, and this is what a printed
# label row reads off it. 1,055,682 declarations, 1,044,332 of them with a
# printed label (98.9%, 2026-09-14).
IMPORT_LEDGER_KEY = ("importer_name", "product_name", "processed_date", "expiry_text")
IMPORT_COLUMNS = (
    *DECLARATION_KEY,
    "declaration_kind",
    "label_text",
)

# The 푸드QR 원재료 feed wraps every name in a 네이버 사전 link and every origin in
# a `<p class="bold">`; stripped, the string is the plain comma list the HACCP
# feed sends. Measured 2026-09-13: all 2,301 rows carry tags.
TAG = re.compile(r"<[^>]+>")

# What the HACCP feed writes when it does not know, and when it knows there is
# nothing. The two are never the same sentence on a screen.
NOT_KNOWN = frozenset({"알수없음", "알 수 없음", "-"})
DECLARED_NONE = frozenset({"없음", "해당없음", "없슴"})
WHITESPACE = re.compile(r"\s+")

# How a printed label declares an allergen when it has no 알레르기 section: the
# substances, then 함유. Measured 2026-09-14 over 1,055,682 rows, 449,609 carry
# one of the two phrasings.
DECLARES_CONTAINS = re.compile(r"[가-힣)\]]\s*함유")

# How a printed label declares allergens when it prints no 알레르기 section:
# the substances then 함유 (`우유, 밀 함유`). Measured 2026-09-14: 449,609 of
# 1,055,682 declarations carry one of the two phrasings.
CONTAINS_PHRASE = re.compile(r"([가-힣][가-힣()\s,·]{0,60}?)\s*함유")

# What a declared allergen is split on in the HACCP feed's one string. Measured
# 2026-09-13 over its 14,664 values: commas and `·` separate, ` 및 ` joins two,
# and a newline appears where the publisher pasted a line break.
#
# **Only outside brackets.** 푸드QR writes `조개류(굴, 가리비)` as one declaration
# and HACCP writes `조개류(굴,홍합,꼬막 포함)`; splitting on every comma turns one
# allergen into three that name no substance.
SEPARATORS = frozenset(",·/\n")
JOINER = " 및 "

# `우유 함유` and `우유` are the same declaration; the suffix is grammar, not a
# name.
CONTAINS_SUFFIX = re.compile(r"\s*함유\s*$")

# What the publisher writes when there is nothing to declare, or nothing known:
# 8,484 of the HACCP feed's 14,664 values read the first of these and 41 the
# second (2026-09-13). Neither is an allergen, so neither becomes a row.
NOT_A_DECLARATION = frozenset({"알수없음", "알 수 없음", "없음", "해당없음", "-", "없슴"})


# The registries that number their reports, and the kind a number in each one
# belongs to. Import labels are not looked up: this repository numbers them.
REGISTRIES = (
    (FoodLedgerItemReport, ledger_item_report.REPORT_KIND),
    (FoodLedgerLivestockItemReportRawMaterial, ledger_livestock.REPORT_KIND),
    (FoodLedgerHealthFunctionalItemReport, ledger_health_functional.REPORT_KIND),
)

# The registry left out, and why: 수입식품 numbers a product by a digest this
# codebase mints (`_import_product`), not by a 품목제조보고번호, so no published
# record can carry one and nothing would ever resolve against it.
UNRESOLVED_REGISTRIES = {"FoodLedgerImportFoodLabel": "번호가 우리가 만드는 digest다"}


# ============================================================
# Classes
# ============================================================


class FoodLabelFamilyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rebuild_label_family(self, synced_by: str) -> int:
        """Write `food_label` and its three children off the label ledgers; return their rows.

        Three registries print labels and one table family holds them:
        `food_label` is the label itself, and `food_label_allergen`,
        `food_label_caution` and `food_label_packaging` are the lists printed on
        it. Every row of all four comes from one reading - the 푸드QR feeds row
        by row, the HACCP feed's one string, and the printed paragraph of each
        imported product's newest declaration, read once and handed to all four.

        Each table is staged and replaced as its own table (`LedgerStage`), so a
        floor refusal on one is that table's, but the four are written in one
        pass because they answer one question and a second pass would read the
        same paragraph a second time.
        """
        stages = {
            "label": LedgerStage(
                self.session, FoodLabel, label_model.NATURAL_KEY, label_model.SYNCED_COLUMNS
            ),
            "allergen": LedgerStage(
                self.session,
                FoodLabelAllergen,
                allergen_model.NATURAL_KEY,
                allergen_model.SYNCED_COLUMNS,
            ),
            "caution": LedgerStage(
                self.session,
                FoodLabelCaution,
                label_caution_model.NATURAL_KEY,
                label_caution_model.SYNCED_COLUMNS,
            ),
            "packaging": LedgerStage(
                self.session,
                FoodLabelPackaging,
                label_packaging_model.NATURAL_KEY,
                label_packaging_model.SYNCED_COLUMNS,
            ),
        }
        async with self.session.begin():
            for stage in stages.values():
                await stage.create()
        try:
            async with self.session.begin():
                printed = await self._import_labels()
                await self._write_label(stages["label"], printed)
                await self._write_allergen(stages["allergen"], printed)
                await self._write_caution(stages["caution"], printed)
                await self._write_packaging(stages["packaging"], printed)
                written = 0
                for stage in stages.values():
                    written += await stage.replace(synced_by, floor=None)
                return written
        finally:
            async with self.session.begin():
                for stage in stages.values():
                    await stage.drop()

    async def _write_label(self, stage: LedgerStage, printed: list[Mapping[str, object]]) -> None:
        """The label itself, from all three registries."""
        storage = await self._text(FoodLedgerQrStorage.label_no, FoodLedgerQrStorage.storage_text)
        raw = await self._text(
            FoodLedgerQrRawMaterial.label_no, FoodLedgerQrRawMaterial.raw_material_html
        )
        reports = await self._reports()
        makers = await self._makers()
        declared = await self._declared()
        registry = await self._registry()
        await stage.add(
            [
                _qr_label(record, storage, raw, reports, makers, declared, registry)
                async for record in await self._stream(FoodLedgerQrLabel)
            ]
        )
        await stage.add(
            [
                _haccp_label(record, registry)
                async for record in await self._stream(FoodLedgerHaccpLabel)
            ]
        )
        await stage.add([_import_label(record) for record in printed])

    async def _registry(self) -> dict[str, str]:
        """Which registry each reported number belongs to - where a label's kind comes from.

        Read off the report ledgers, not off `food_item_report`: a derivation is
        a function of the ledgers, and one that read another derived table would
        depend on the order `DERIVATIONS` writes them in (rule://backend-ledger).
        An import label needs no lookup - this repository numbered it.

        Measured 2026-09-15 over the 16,938 푸드QR and HACCP labels that name a
        number: 8,033 domestic, 1,938 livestock, 49 health_functional.
        """
        registry: dict[str, str] = {}
        for model, kind in REGISTRIES:
            rows = await self.session.execute(select(model.item_report_no))
            registry.update({number: kind for (number,) in rows.all()})
        return registry

    async def _write_allergen(
        self, stage: LedgerStage, printed: list[Mapping[str, object]]
    ) -> None:
        """What each label declares, numbered from 1 in the order it was printed."""
        declared: dict[tuple[str, str], list[str]] = {}
        qr_rows = await self.session.execute(
            select(FoodLedgerQrAllergy.label_no, FoodLedgerQrAllergy.allergen_name).order_by(
                FoodLedgerQrAllergy.label_no, FoodLedgerQrAllergy.allergen_serial
            )
        )
        for label_no, name in qr_rows.all():
            _collect(declared, (allergen_model.FOOD_QR_SOURCE, label_no), _names(name))
        haccp_rows = await self.session.execute(
            select(
                FoodLedgerHaccpLabel.item_report_no, FoodLedgerHaccpLabel.allergy_names
            ).order_by(FoodLedgerHaccpLabel.item_report_no)
        )
        for item_report_no, names in haccp_rows.all():
            _collect(declared, (allergen_model.HACCP_SOURCE, item_report_no), _names(names))
        for row in printed:
            _collect(
                declared,
                (allergen_model.IMPORT_SOURCE, digest(PRODUCT_PREFIX, row, PRODUCT_KEY)),
                _printed(str(row.get("label_text") or "")),
            )
        await stage.add(
            [
                {"source": source, "label_key": key, "position": position, "name": name}
                for (source, key), names in declared.items()
                for position, name in enumerate(names, start=1)
            ]
        )

    async def _write_caution(self, stage: LedgerStage, printed: list[Mapping[str, object]]) -> None:
        """The 주의사항 each label prints, numbered from 1."""
        rows = await self.session.stream(
            select(FoodLedgerQrCaution).order_by(
                FoodLedgerQrCaution.label_no, FoodLedgerQrCaution.detail_serial
            )
        )
        position = 0
        current: str | None = None
        page: list[dict[str, object]] = []
        async for (record,) in rows:
            if record.label_no != current:
                current, position = record.label_no, 0
            position += 1
            page.append(
                {
                    "source": label_caution_model.FOOD_QR_SOURCE,
                    "label_key": record.label_no,
                    "position": position,
                    "caution_text": record.caution_text,
                }
            )
            if len(page) >= PAGE_SIZE:
                await stage.add(page)
                page = []
        if page:
            await stage.add(page)
        await stage.add([row for record in printed for row in _caution_rows(record)])

    async def _write_packaging(
        self, stage: LedgerStage, printed: list[Mapping[str, object]]
    ) -> None:
        """The 포장재질 each label prints, numbered from 1."""
        rows = await self.session.stream(
            select(FoodLedgerQrPackaging).order_by(
                FoodLedgerQrPackaging.label_no,
                FoodLedgerQrPackaging.detail_serial,
                FoodLedgerQrPackaging.item_report_serial,
            )
        )
        position = 0
        current: str | None = None
        page: list[dict[str, object]] = []
        async for (record,) in rows:
            if record.label_no != current:
                current, position = record.label_no, 0
            position += 1
            page.append(
                {
                    "source": label_packaging_model.FOOD_QR_SOURCE,
                    "label_key": record.label_no,
                    "position": position,
                    "packaging_text": record.packaging_text,
                }
            )
            if len(page) >= PAGE_SIZE:
                await stage.add(page)
                page = []
        if page:
            await stage.add(page)
        await stage.add([row for record in printed for row in _packaging_rows(record)])

    async def _import_labels(self) -> list[Mapping[str, object]]:
        """One printed label per imported product - its newest declaration that printed one.

        1,044,179 declarations carry a paragraph and they describe 289,938
        products (2026-09-14): the same product is declared 3.6 times on
        average, 1,226 times at the widest, and 101,150 of the 142,370 products
        with several declarations print the identical paragraph every time. A
        label per declaration showed one package a thousand times over; a
        product's label is the newest one printed for it, and the declarations
        themselves stay whole in `food_item_report_declaration`.

        Read once for the whole family: the four tables are four readings of
        this one list.
        """
        held: dict[str, tuple[str, Mapping[str, object]]] = {}
        async for page in scan_table(
            self.session,
            FoodLedgerImportFoodLabel,
            IMPORT_LEDGER_KEY,
            IMPORT_COLUMNS,
            PAGE_SIZE,
            where=FoodLedgerImportFoodLabel.declaration_kind.in_(
                ledger_import.PRODUCT_DECLARATION_KINDS
            ),
        ):
            for record in page:
                if not record.get("label_text"):
                    continue
                keep_newest(
                    held,
                    digest(PRODUCT_PREFIX, record, PRODUCT_KEY),
                    str(record.get("processed_date") or ""),
                    record,
                )
        return [record for _, record in held.values()]

    async def _stream(self, model: type[FoodLedgerQrLabel] | type[FoodLedgerHaccpLabel]):
        """One ledger's rows, one at a time."""
        rows = await self.session.stream(select(model))
        return (record async for (record,) in rows)

    async def _text(self, key_column, text_column) -> dict[str, str]:
        """A sibling ledger as {label: its text}, newline-joined where the label repeats."""
        rows = await self.session.execute(
            select(key_column, text_column).where(text_column.is_not(None))
        )
        joined: dict[str, str] = {}
        for key, text in rows.all():
            cleaned = WHITESPACE.sub(" ", TAG.sub("", text)).strip()
            if not cleaned:
                continue
            joined[key] = cleaned if key not in joined else f"{joined[key]}\n{cleaned}"
        return joined

    async def _declared(self) -> set[str]:
        """The 푸드QR labels whose 알레르기 feed carries at least one row.

        The feed publishes 1,746 labels (2026-09-13) against the 2,276 the
        표시사항 feed knows, so a label's absence from it is not a declaration
        of `없음` - it is the portal saying nothing, which is what
        `ALLERGEN_UNKNOWN` records.
        """
        rows = await self.session.execute(select(FoodLedgerQrAllergy.label_no).distinct())
        return {label_no for (label_no,) in rows.all()}

    async def _reports(self) -> dict[str, str]:
        """Each label's 품목보고번호, from whichever of the two feeds carries it.

        The 영양표시 feed states it on all 25,663 of its rows and the 품목제조정보
        feed on all 2,976 of its own (2026-09-13); read together they cover 2,786
        of the 4,765 라벨 the family knows.
        """
        found: dict[str, str] = {}
        for key, number in (
            *(
                await self.session.execute(
                    select(
                        FoodLedgerQrNutrition.label_no, FoodLedgerQrNutrition.item_report_no
                    ).where(FoodLedgerQrNutrition.item_report_no.is_not(None))
                )
            ).all(),
            *(
                await self.session.execute(
                    select(
                        FoodLedgerQrManufacture.label_no, FoodLedgerQrManufacture.item_report_no
                    ).where(FoodLedgerQrManufacture.item_report_no.is_not(None))
                )
            ).all(),
        ):
            found[key] = number
        return found

    async def _makers(self) -> dict[str, tuple[str | None, str | None, str | None]]:
        """Each label's 업소명, 대표자 and 소재지 - the columns only 품목제조정보 carries."""
        rows = await self.session.execute(
            select(
                FoodLedgerQrManufacture.label_no,
                FoodLedgerQrManufacture.business_name,
                FoodLedgerQrManufacture.representative_name,
                FoodLedgerQrManufacture.site_address,
            )
        )
        return {
            key: (business, representative, address)
            for key, business, representative, address in rows.all()
        }


# ============================================================
# Functions
# ============================================================


def _qr_label(
    record: FoodLedgerQrLabel,
    storage: dict[str, str],
    raw: dict[str, str],
    reports: dict[str, str],
    makers: dict[str, tuple[str | None, str | None, str | None]],
    declared: set[str],
    registry: dict[str, str],
) -> dict[str, object]:
    """One 푸드QR 표시사항 row plus what its four sibling feeds say about the same label."""
    business, representative, address = makers.get(record.label_no, (None, None, None))
    number = reports.get(record.label_no)
    return {
        "source": label_model.FOOD_QR_SOURCE,
        "label_key": record.label_no,
        "report_kind": None if number is None else registry.get(number),
        "item_report_no": number,
        "allergen_declaration": (
            label_model.ALLERGEN_DECLARED
            if record.label_no in declared
            else label_model.ALLERGEN_UNKNOWN
        ),
        "product_name": record.product_name,
        "barcode_no": record.barcode_no,
        "food_division_name": record.food_division_name,
        "food_type_name": record.food_type_name,
        "product_type_state": None,
        "content_amount_text": record.content_amount_text,
        "shelf_life_text": record.shelf_life_text,
        "storage_text": storage.get(record.label_no),
        "raw_material_text": raw.get(record.label_no),
        "intake_method_text": record.intake_method_text,
        "functional_info_text": record.functional_info_text,
        "business_name": business,
        "maker_name": None,
        "seller_name": None,
        "representative_name": representative,
        "site_address": address,
        "version_no": record.version_no,
        "valid_from": record.valid_from,
        "valid_to": record.valid_to,
        "history_tracked_yn": record.history_tracked_yn,
        "irradiated_yn": record.irradiated_yn,
        "gmo_yn": record.gmo_yn,
        "infant_sale_marked_yn": record.infant_sale_marked_yn,
        "high_calorie_low_nutrition_yn": record.high_calorie_low_nutrition_yn,
        "pasteurized_yn": record.pasteurized_yn,
        "sterilized_yn": record.sterilized_yn,
        "refrigerated_yn": record.refrigerated_yn,
    }


def _declaration(text: str | None) -> str:
    """What a HACCP row's 알레르기유발물질 column amounts to.

    Three answers, because the feed gives three: a list of substances, the word
    없음, or 알수없음 - and the last one is the publisher saying it does not
    know. Measured 2026-09-13 over its 14,664 rows: 6,115 list something, 41 say
    없음 and 8,479 say 알수없음.
    """
    stripped = "" if text is None else text.strip()
    if stripped in NOT_KNOWN or not stripped:
        return label_model.ALLERGEN_UNKNOWN
    if stripped in DECLARED_NONE:
        return label_model.ALLERGEN_NONE
    return label_model.ALLERGEN_DECLARED


def _haccp_label(record: FoodLedgerHaccpLabel, registry: dict[str, str]) -> dict[str, object]:
    """One HACCP row as a label: the columns that feed answers, and NULL for the rest.

    The 여부 flags, the 소비기한 and the 유효기간 are 푸드QR's columns; this portal
    publishes none of them, and a NULL says so where a default would invent it.
    """
    return {
        "source": label_model.HACCP_SOURCE,
        "label_key": record.item_report_no,
        "report_kind": registry.get(record.item_report_no),
        "item_report_no": record.item_report_no,
        "allergen_declaration": _declaration(record.allergy_names),
        "product_name": record.product_name,
        "barcode_no": None,
        "food_division_name": record.product_kind_division,
        "food_type_name": record.product_type_name,
        "product_type_state": record.product_type_state,
        "content_amount_text": record.capacity_text,
        "shelf_life_text": None,
        "storage_text": None,
        "raw_material_text": record.raw_material_names,
        "intake_method_text": None,
        "functional_info_text": None,
        "business_name": None,
        "maker_name": record.maker_name,
        "seller_name": record.seller_name,
        "representative_name": None,
        "site_address": None,
        "version_no": None,
        "valid_from": None,
        "valid_to": None,
        "history_tracked_yn": None,
        "irradiated_yn": None,
        "gmo_yn": None,
        "infant_sale_marked_yn": None,
        "high_calorie_low_nutrition_yn": None,
        "pasteurized_yn": None,
        "sterilized_yn": None,
        "refrigerated_yn": None,
    }


def _import_label(row: Mapping[str, object]) -> dict[str, object]:
    """One 수입신고's printed label, read out of the paragraph the feed publishes.

    Keyed by the declaration's digest, not the product's: the same product is
    declared 3.6 times on average and the packages differ - 내용량 and 포장재질
    are what a particular import printed. The columns the other two portals
    carry as fields (바코드, 유효기간, the 여부 flags) are NULL here, because a
    printed label states none of them.
    """
    printed_text = str(row["label_text"])
    return {
        "source": label_model.IMPORT_SOURCE,
        # The product's number, not the declaration's: one product prints one
        # label, whatever the border paperwork counted. Its registry needs no
        # lookup - this repository numbered it, under the import kind.
        "label_key": digest(PRODUCT_PREFIX, row, PRODUCT_KEY),
        "report_kind": ledger_import_food_label.REPORT_KIND,
        "item_report_no": digest(PRODUCT_PREFIX, row, PRODUCT_KEY),
        "allergen_declaration": _printed_declaration(printed_text),
        "product_name": row.get("product_name"),
        "barcode_no": None,
        "food_division_name": row.get("declaration_kind"),
        "food_type_name": row.get("product_type_name"),
        "product_type_state": None,
        "content_amount_text": printed_section(printed_text, "amount"),
        "shelf_life_text": printed_section(printed_text, "shelf_life"),
        "storage_text": printed_section(printed_text, "storage"),
        "raw_material_text": printed_section(printed_text, "ingredients"),
        "intake_method_text": printed_section(printed_text, "intake"),
        "functional_info_text": printed_section(printed_text, "nutrition"),
        "business_name": row.get("importer_name"),
        "maker_name": row.get("overseas_maker_name"),
        "seller_name": None,
        "representative_name": None,
        "site_address": None,
        "version_no": None,
        "valid_from": None,
        "valid_to": None,
        "history_tracked_yn": None,
        "irradiated_yn": None,
        "gmo_yn": None,
        "infant_sale_marked_yn": None,
        "high_calorie_low_nutrition_yn": None,
        "pasteurized_yn": None,
        "sterilized_yn": None,
        "refrigerated_yn": None,
    }


def _printed_declaration(text: str) -> str:
    """Whether a printed label declares allergens, says there are none, or says nothing.

    A printed label has no field for this: it prints `… 우유, 밀 함유` or an
    `알레르기 :` section, and most labels print neither. Measured 2026-09-14:
    449,609 of 1,055,682 rows carry one of the two phrasings (42.6%), so the
    rest are UNKNOWN rather than `none` - the same distinction the HACCP feed
    forced.
    """
    if printed_names(printed_section(text, "allergen")) or DECLARES_CONTAINS.search(text or ""):
        return label_model.ALLERGEN_DECLARED
    return label_model.ALLERGEN_UNKNOWN


def _collect(
    declared: dict[tuple[str, str], list[str]], key: tuple[str, str], names: list[str]
) -> None:
    """Add a label's names, keeping the order they arrived in and dropping repeats."""
    held = declared.setdefault(key, [])
    for name in names:
        if name not in held:
            held.append(name)


def _names(text: str | None) -> list[str]:
    """One declaration as the allergens it names, or nothing at all.

    The name is kept as the publisher wrote it - `소고기` is not folded onto
    `쇠고기`, `난류` not onto `알류` (379 distinct names over the HACCP feed
    against 푸드QR's 74, 2026-09-13). Folding them onto the 22 법정 names would
    be this harness making a safety claim the package did not.

    Two repairs only: the `함유` suffix comes off, and a fragment whose brackets
    do not close is cut back to the last balanced character (114 values read
    `조개류(굴` where a split landed inside a bracket).
    """
    if text is None:
        return []
    names: list[str] = []
    for part in split_list(text.replace(JOINER, ","), SEPARATORS):
        name = _balanced(CONTAINS_SUFFIX.sub("", part).strip())
        if name and name not in NOT_A_DECLARATION:
            names.append(name)
    return names


def _balanced(name: str) -> str:
    """The name up to the point its brackets stop balancing."""
    depth = 0
    for index, character in enumerate(name):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return name[:index].strip()
    return name if depth == 0 else name[: name.index("(")].strip()


def _printed(text: str) -> list[str]:
    """The allergens a printed label declares, from its section or its 함유 phrase.

    Two phrasings and nothing else is read: a label that prints neither declares
    nothing here, which is what `food_label.allergen_declaration` records as
    UNKNOWN rather than as `없음`.
    """
    named = printed_names(printed_section(text, "allergen"))
    if named:
        return [name for name in named if name not in NOT_A_DECLARATION]
    found: list[str] = []
    for phrase in CONTAINS_PHRASE.findall(text):
        for name in printed_names(phrase):
            if name not in NOT_A_DECLARATION and name not in found:
                found.append(name)
    return found


def _caution_rows(record: Mapping[str, object]) -> list[dict[str, object]]:
    """One import declaration's printed 주의사항 parts, numbered from 1."""
    text = record.get("label_text")
    section = printed_section(text if isinstance(text, str) else None, "caution")
    parts = printed_parts(section)
    key = digest(PRODUCT_PREFIX, record, PRODUCT_KEY)
    return [
        {
            "source": label_caution_model.IMPORT_SOURCE,
            "label_key": key,
            "position": position,
            "caution_text": part,
        }
        for position, part in enumerate(parts, start=1)
    ]


def _packaging_rows(record: Mapping[str, object]) -> list[dict[str, object]]:
    """One import declaration's printed 포장재질 parts, numbered from 1."""
    text = record.get("label_text")
    section = printed_section(text if isinstance(text, str) else None, "packaging")
    parts = printed_names(section)
    key = digest(PRODUCT_PREFIX, record, PRODUCT_KEY)
    return [
        {
            "source": label_packaging_model.IMPORT_SOURCE,
            "label_key": key,
            "position": position,
            "packaging_text": part,
        }
        for position, part in enumerate(parts, start=1)
    ]
