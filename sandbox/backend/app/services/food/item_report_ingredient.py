# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import LedgerStage, scan_table
from app.core.printed_label import printed_names, printed_section, split_list
from app.models.base import Base
from app.models.food import item_report_ingredient as ingredient
from app.models.food import ledger_import_food_label as ledger_import
from app.models.food.item_report_ingredient import FoodItemReportIngredient
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.models.food.ledger_item_report_raw_material import FoodLedgerItemReportRawMaterial
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.models.food.ledger_raw_material import FoodLedgerRawMaterial
from app.services.food.item_report_declaration import PRODUCT_KEY, PRODUCT_PREFIX, digest


# ============================================================
# Constants
# ============================================================

# The ledgers are read in pages of this many records; a page splits into a few
# thousand ingredient rows at most (262 on the widest product, ~6 on the mean).
PAGE_SIZE = 1000

# The three lists 건강기능식품 publishes, and what each one is: 기능성 원재료 is
# what the product claims its function from, 기타 원재료 the rest of the recipe,
# 캡슐 원재료 the shell it is packed in. Measured 2026-09-15 over 46,086 reports:
# 46,084 carry the first, 41,764 the second, 12,482 the third. Three lists, three
# roles, one table - the role is the row's, so a reader can ask for the
# functional ones alone.
HEALTH_FUNCTIONAL_LISTS = (
    ("functional", "functional_raw_material_names"),
    ("other", "other_raw_material_names"),
    ("capsule", "capsule_raw_material_names"),
)
HEALTH_FUNCTIONAL_COLUMNS = ("item_report_no", *(column for _, column in HEALTH_FUNCTIONAL_LISTS))

# The key both ledgers carry a report under, and the two lists each carries.
LEDGER_KEY = ("item_report_no",)
LEDGER_COLUMNS = ("raw_material_names", "raw_material_ordinals")

# The import slice reads a **printed** list instead of two joined columns: the
# feed's own `IRDNT_NM` is filled on 7,645 of 1,055,682 declarations (0.7%),
# while the printed 원재료명 section is on 504,474 (47.8%) and yields 2,487,916
# names, 4.9 per label (measured 2026-09-14). A product's ingredients are taken
# from its **newest** declaration, because the list is the package's and the
# newest package is the one on shelves; 292,867 products carry a list under
# 168,142 of them - the rest print none, and none is what they get.
IMPORT_LEDGER_KEY = ("importer_name", "product_name", "processed_date", "expiry_text")
IMPORT_COLUMNS = (
    *PRODUCT_KEY,
    "processed_date",
    "label_text",
)

# Which ledger fills which slice. Two registries, two number spaces, so the
# kind is stamped on every row of a ledger's split.
SOURCES: tuple[tuple[str, type[Base]], ...] = (
    (ingredient.DOMESTIC_KIND, FoodLedgerItemReportRawMaterial),
    (ingredient.LIVESTOCK_KIND, FoodLedgerLivestockItemReportRawMaterial),
)

# Every joined list here - C002 and C006's `RAWMTRL_NM`/`RAWMTRL_ORD`, the three
# 건강기능식품 lists, the registry's own 이명 column - is split by one function,
# `core.printed_label.split_list`, which counts depth over every bracket pair and
# leaves a thousands comma alone. Measured over the whole C002 ledger
# (2026-09-07): splitting on every comma listed more names than ordinals on
# 14,645 rows, 12,712 of them because a name carries a comma inside its brackets
# (`혼합제제(밀가루, 정제수)`); counting only `()` then cut 건기식 기능성 원재료
# at the braces and at `100,000,000,000개/g` (2026-09-15, 118 + 279 rows).
# The 이명 column is comma-joined by the registry itself and splits the same way.

# How a label's name is keyed against the registry. Whitespace is never a
# difference (`밀 가루`, and the registry itself lists 비타민B12혼합제제분말
# twice, once with spaces). Brackets on the *label* are what the 표시기준
# puts there - an origin, a share, a flavour name (`밀가루(미국산)`,
# `합성향료(딸기향)`) - so they are a second chance after the exact name. The
# registry's own brackets are never stripped: 합성향료(바닐라향) and
# 합성향료(딸기향) are 2,303 distinct B codes whose names differ only inside
# them, and a key that strips both sides collapses all of them onto the one
# generic 합성향료 entry (measured 2026-09-09, 176,056 rows).
EXACT_KEY = re.compile(r"\s")
LOOSE_KEY = re.compile(r"\s|\([^)]*\)")

# What a **printed** label writes around a name that the registry does not.
# Measured 2026-09-14 over the 126,321 import ingredient rows that resolved to
# no code: a bracketed tail naming the allergen it carries ("냉동돼지고기 [돼지고기
# 함유]", 2,313 rows on one name alone), the 용도 the 표시기준 asks for
# ("무수아황산(산화방지제)", 877), the same 용도 written the other way round
# ("보존료(소브산칼륨)", 274), the 5' of a nucleotide lost in the printing
# ("'-리보뉴클레오티드이나트륨", 991 - the registry writes 5-리보뉴클레오티드이나트륨),
# and the roman numeral written in the other alphabet ("카라멜색소Ⅰ" against the
# registry's "카라멜색소 I", 442). None of these changes the **name**: they are
# dropped from the resolution key only, and the row keeps what the label printed.
TAIL_NOTE = re.compile(r"[\[{（][^\]}）]*[\]}）]")
USE_LABEL = (
    "산화방지제",
    "보존료",
    "합성보존료",
    "감미료",
    "착색료",
    "발색제",
    "산도조절제",
    "유화제",
    "향미증진제",
    "팽창제",
    "증점제",
    "안정제",
    "응고제",
    "표백제",
    "살균제",
    "영양강화제",
    "고결방지제",
    "피막제",
    "추출용제",
    "껌기초제",
    "여과보조제",
    "소포제",
    "이형제",
    "밀가루개량제",
    "착향료",
    "합성향료",
)
USE_SUFFIX = re.compile(r"\((?:" + "|".join(USE_LABEL) + r")\)")
USE_PREFIX = re.compile(r"^(?:" + "|".join(USE_LABEL) + r")\(([^)]*)\)$")
# The 용도 written as a trailing bracket, however nested or spaced:
# `포도원액(무수아황산(산화방지제))` and `포도원액 (무수아황산(산화방지제))` are
# 포도원액 (396 + 3,539 rows, measured 2026-09-14). Only the last group goes -
# `치즈(우유, 유산균)` keeps its own list, which the registry carries too.
TRAILING_GROUP = re.compile(r"\s*\([^()]*(?:\([^()]*\)[^()]*)*\)\s*$")
NUCLEOTIDE = re.compile(r"^5?['’`]-")
ROMAN_WIDE = {"Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V"}
ROMAN_ASCII = (("IV", "Ⅳ"), ("III", "Ⅲ"), ("II", "Ⅱ"), ("V", "Ⅴ"), ("I", "Ⅰ"))

# Spellings the label uses and the registry does not, each one taken from the
# unresolved list and confirmed against the registry (2026-09-14): 고추가루 714
# rows, 무우 334, 쇠고기 727. Nothing is in this table that was not measured on
# both sides - a guessed alias would resolve a name to the wrong code.
ALIASES = {"고추가루": "고춧가루", "무우": "무", "쇠고기": "소고기"}

# **What the 건강기능식품 registry writes around a name, and what it costs to
# strip it.** Measured 2026-09-15 over the 663,361 names its three lists split
# into (12,797 distinct), and then re-resolved with each rule as an extra key:
#
# | written form | names | extra codes resolved |
# | --- | --- | --- |
# | `(고시형)` | 123,215 | +1 |
# | 괄호 안 함량·적량·이상 | 842 + 366 + 814 | +6 |
# | 괄호 없는 꼬리 함량 | 1,863 | +32 |
#
# So none of them is a rule here. `(고시형)` is **the registry's own word**:
# 42,432 I2520 rows include names carrying it, and stripping it as a
# *replacement* dropped resolution from 98.41 % to 93.84 % (652,821 → 622,560
# names). As a fallback key the three rules together buy 39 names of 663,361 -
# 0.006 % - which is not worth a rule that a reader must then keep true.
# The 10,501 that resolve to nothing are 고시형 기능성 원료 vocabulary the I2520
# 원재료 dictionary does not carry (무수구연산 833, 프로바이오틱스 336 at the head
# of the tail); they stay NULL, because a code forced onto them would be a
# guess (rule://backend-ledger).
#
# When one name matches several codes, the class the material is filed
# under decides: an ingredient called 밀가루 is the 원료 (A) before it is the
# 식품유형 (P) of the same name; 구연산 is the 첨가물 (B); a 주용도 written as
# the 표시기준 allows (산도조절제, 유화제, 향미증진제) is the registry's own
# 복합원료 (U) entry for that purpose. Measured 2026-09-09 over 10,135,733
# rows: 9,912,480 resolve on the exact name, 5,195 more once the label's
# brackets are dropped, 1,983 by the verbatim tiebreak; 8,273 are ties among
# retired codes and 207,736 match nothing - both left NULL, never guessed.
# The rebuilt table agrees: 9,921,636 of 10,129,352 rows carry a code.
#
# These five are also the whole of what a code may resolve to: the registry
# is read off its ledger (a derivation is a function of the ledgers), and the
# ledger carries 기구·용기포장 (D) and 위생용품 (E) too - the two classes the
# raw material derivation drops (`raw_material.NOT_AN_INGREDIENT`). A code of
# a class not listed here is no candidate, so the two rules agree by
# construction and a resolved code is always a row of `food_raw_material`.
CLASS_RANK = {"A": 0, "B": 1, "C": 2, "U": 3, "P": 4}


# ============================================================
# Classes
# ============================================================


class _Material(NamedTuple):
    """What the resolver ranks a registry code by."""

    code: str
    name: str
    in_use: bool


class _Registry:
    """The raw material registry as a name index, built once and asked ten million times.

    Two indexes, because the registry publishes two kinds of name. `by_key` is
    the 대표 원재료명 - what a code is called. `by_alias` is the 이명 column the
    registry states itself, comma-joined: 15,825 of its 42,432 rows carry one
    (2026-09-14), and they are the spellings a label actually prints -
    우유응고효소 lists RENNET/레넷/렌넷, d-α-토코페롤 lists sixty forms of itself.
    A guessed alias would resolve a name to the wrong code; a published one is
    the registry's own statement, so it is a lookup and not a guess. Matched
    without spaces and case-insensitively, because that is the only difference
    between `D-a-토코페롤` and `d-a-토코페롤`.
    """

    def __init__(self, rows: list[tuple[str, str | None, str | None, str | None]]) -> None:
        self.by_key: dict[str, list[_Material]] = {}
        self.by_alias: dict[str, list[_Material]] = {}
        for code, name, use_yn, alias in rows:
            if name is None or code[:1] not in CLASS_RANK:
                continue
            material = _Material(code, name, use_yn == "Y")
            self.by_key.setdefault(EXACT_KEY.sub("", name), []).append(material)
            for part in split_list(alias):
                key = EXACT_KEY.sub("", part).lower()
                if key:
                    self.by_alias.setdefault(key, []).append(material)


class FoodItemReportIngredientService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rebuild_item_report_ingredient(self, synced_by: str) -> int:
        """Write `food_item_report_ingredient` off the two 원재료 ledgers; return its rows.

        Each ledger's comma-joined 원재료명 / 원재료표시순서 split into one row
        per ingredient (`_ingredients`), under that ledger's kind. Read
        off the live ledgers in keyed pages, staged, and written over whole in
        one short transaction (`LedgerStage.replace`, no floor: each ledger's
        own floor already vouched for its records). Measured 2026-09-08: C002
        1,072,302 records → 8,724,566 rows and C006 567,910 → 1,411,169; a
        rebuild from the live ledgers is minutes, against the hours of a walk.

        The third slice is `import`, and it is read differently: there is no
        원재료 column to split, only the printed label, so the list comes from
        the 원재료명 section of the product's newest declaration
        (`core/printed_label.py`).
        """
        stage = LedgerStage(
            self.session,
            FoodItemReportIngredient,
            ingredient.NATURAL_KEY,
            ingredient.SYNCED_COLUMNS,
        )
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                registry = await self._registry()
                for kind, ledger in SOURCES:
                    async for page in scan_table(
                        self.session, ledger, LEDGER_KEY, LEDGER_COLUMNS, PAGE_SIZE
                    ):
                        await stage.add(
                            [row for record in page for row in _split(record, kind, registry)]
                        )
                async for page in scan_table(
                    self.session,
                    FoodLedgerHealthFunctionalItemReport,
                    LEDGER_KEY,
                    HEALTH_FUNCTIONAL_COLUMNS,
                    PAGE_SIZE,
                ):
                    await stage.add(
                        [
                            row
                            for record in page
                            for row in _health_functional_rows(record, registry)
                        ]
                    )
                for number, names in (await self._printed_lists()).items():
                    await stage.add(
                        [
                            {
                                "report_kind": ingredient.IMPORT_KIND,
                                "item_report_no": number,
                                "position": position,
                                "ordinal": None,
                                "name": name,
                                "material_code": _resolve(registry, name),
                                "ingredient_role": None,
                            }
                            for position, name in enumerate(names, start=1)
                        ]
                    )
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()

    async def _printed_lists(self) -> dict[str, list[str]]:
        """Each import product's 원재료 list, taken from its newest declaration.

        `ordinal` is None on every row: a printed list has an order but no
        published 원재료표시순서, and a number invented from the order would read
        as the registry's.
        """
        held: dict[str, tuple[str, list[str]]] = {}
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
                text = record.get("label_text")
                names = printed_names(
                    printed_section(text if isinstance(text, str) else None, "ingredients")
                )
                if not names:
                    continue
                number = digest(PRODUCT_PREFIX, record, PRODUCT_KEY)
                processed = str(record.get("processed_date") or "")
                seen = held.get(number)
                if seen is not None and seen[0] >= processed:
                    continue
                held[number] = (processed, names)
        return {number: names for number, (_, names) in held.items()}

    async def _registry(self) -> _Registry:
        """The I2520 ledger as it stands - the same rows the raw material derivation reads."""
        rows = await self.session.execute(
            select(
                FoodLedgerRawMaterial.raw_material_code,
                FoodLedgerRawMaterial.representative_raw_material_name,
                FoodLedgerRawMaterial.use_yn,
                FoodLedgerRawMaterial.raw_material_alias,
            )
        )
        return _Registry([(code, name, use_yn, alias) for code, name, use_yn, alias in rows.all()])


# ============================================================
# Functions
# ============================================================


def _resolve(registry: _Registry, name: str) -> str | None:
    """The one code this label name means, or None when there is none or the rule cannot pick.

    The exact name first, the name without its brackets second; among the
    matches the in-use codes before the retired, then the class by
    `CLASS_RANK`, then the code whose registry name is the label's name
    character for character; a tie that survives all three is left NULL.
    """
    keys = _resolution_keys(name)
    candidates: list[_Material] = []
    for key in keys:
        candidates = registry.by_key.get(key) or []
        if candidates:
            break
    if not candidates:
        # The registry's own 이명 column, after every reading of the name: a
        # published alias is a statement, so it answers where the 대표명 does not.
        for key in keys:
            candidates = registry.by_alias.get(key.lower()) or []
            if candidates:
                break
    if not candidates:
        return None
    in_use = [material for material in candidates if material.in_use]
    pool = in_use or candidates
    best = min(_class_rank(material) for material in pool)
    winners = [material for material in pool if _class_rank(material) == best]
    if len(winners) > 1:
        verbatim = [material for material in winners if material.name == name]
        winners = verbatim or winners
    # The registry repeats itself: 우유응고효소 lists RENNET twice and Chymosin
    # twice in one 이명 column (2026-09-14), so several winners may be one code -
    # a tie is two *codes*, not two readings of the same one.
    codes = {material.code for material in winners}
    return winners[0].code if len(codes) == 1 else None


def _resolution_keys(name: str) -> list[str]:
    """Every key this printed name may be looked up under, closest reading first.

    The label's own spelling first, then what the 표시기준 made it print around
    the name: the bracketed allergen note, the 용도 in either position, the
    dropped 5' of a nucleotide, the roman numeral in the other alphabet, and the
    measured aliases. Measured 2026-09-14 over the 126,321 rows that resolved to
    nothing: 19,884 of them reach a registry name this way, 8,075 of which the
    exact and loose keys alone never reached.
    """
    keys: list[str] = []

    def _add(key: str | None) -> None:
        if key and key not in keys:
            keys.append(key)

    _add(EXACT_KEY.sub("", name))
    _add(LOOSE_KEY.sub("", name))
    stripped = TAIL_NOTE.sub("", name).strip()
    _add(EXACT_KEY.sub("", stripped))
    _add(LOOSE_KEY.sub("", stripped))
    _add(EXACT_KEY.sub("", USE_SUFFIX.sub("", stripped)))
    _add(EXACT_KEY.sub("", TRAILING_GROUP.sub("", stripped)))
    inner = USE_PREFIX.match(EXACT_KEY.sub("", stripped))
    if inner is not None:
        _add(inner.group(1))
    if NUCLEOTIDE.match(stripped):
        _add(EXACT_KEY.sub("", "5-" + NUCLEOTIDE.sub("", stripped)))
    _add(EXACT_KEY.sub("", "".join(ROMAN_WIDE.get(letter, letter) for letter in stripped)))
    base = EXACT_KEY.sub("", stripped)
    for ascii_form, wide_form in ROMAN_ASCII:
        if base.endswith(ascii_form):
            _add(base[: -len(ascii_form)] + wide_form)
            break
    _add(ALIASES.get(base))
    return keys


def _class_rank(material: _Material) -> int:
    return CLASS_RANK[material.code[:1]]


def _health_functional_rows(
    record: Mapping[str, object], registry: _Registry
) -> list[dict[str, object]]:
    """One 건강기능식품 report's three lists as ingredient rows, each under its role.

    The lists are numbered as one sequence in the order the registry publishes
    them (기능성 → 기타 → 캡슐), because `position` is what makes a name unique
    within a report and a name may appear in two of the lists. The names carry
    the registry's own notes - `Lactobacillus acidophilus(고시형)` - which the
    resolver's bracket rules read the same way they read a printed label's.

    **The fourth column of names, 기능지표성분 (`RAWMTRL_NM`), is not rowed
    here.** It reads like a list (46,073 of 46,086 reports, 158,791 names,
    2026-09-15) but it is a different vocabulary: only 45.2% of its names
    resolve against the I2520 원재료 dictionary, against 97.5% / 98.1% / 99.3%
    for the three lists above, and only 4.2% of them also appear in the
    product's own 기능성 원재료 list. What does not resolve is what the
    vocabulary is - 아연 (12,293), 비타민 B6 (7,824), 프로바이오틱스 (6,536):
    고시형 기능성 원료 and 지표성분 names, the axis the claim is indexed on,
    not the recipe. It equals the report's 품목유형 on 16,756 rows and refines
    it on the rest (15,182 distinct forms against 504 품목유형). Rowing it would
    put a second vocabulary in this table at half the code coverage; it stays a
    field of the product (`food_item_report.functional_indicator`).
    """
    rows: list[dict[str, object]] = []
    for role, column in HEALTH_FUNCTIONAL_LISTS:
        for name in split_list(record.get(column)):
            rows.append(
                {
                    "report_kind": ingredient.HEALTH_FUNCTIONAL_KIND,
                    "item_report_no": record["item_report_no"],
                    "position": len(rows) + 1,
                    "ordinal": None,
                    "name": name,
                    "material_code": _resolve(registry, name),
                    "ingredient_role": role,
                }
            )
    return rows


def _split(record: Mapping[str, object], kind: str, registry: _Registry) -> list[dict[str, object]]:
    """One record's two lists as ingredient rows of its kind, each name resolved to a code."""
    return [
        {
            "report_kind": kind,
            "item_report_no": record["item_report_no"],
            "position": position,
            "ordinal": ordinal,
            "name": name,
            "material_code": _resolve(registry, name),
            # One list, so no role: the column says which of several a name came
            # from, and these registries publish one (rule://backend-ledger).
            "ingredient_role": None,
        }
        for position, ordinal, name in _ingredients(
            record["raw_material_names"], record["raw_material_ordinals"]
        )
    ]


def _ingredients(names: object, ordinals: object) -> list[tuple[int, int | None, str]]:
    """A record's 원재료 lists as (position, ordinal, name) - one per name, in the order sent.

    `position` counts the names from 1 and is what makes a name unique within
    the record (`당절임, 당절임` is two). `ordinal` is the provider's
    원재료표시순서 at the same position when the two lists are the same length
    and every ordinal is an integer, and None for every name of the record
    otherwise (5,712 C002 records, 0.5%, measured 2026-09-07): pairing lists
    of different lengths would put a real-looking number on a guess. A record
    with no names has no ingredients, whatever its ordinals say (3 C002 rows).
    """
    name_items = split_list(names)
    ordinal_items = split_list(ordinals)
    paired: list[int | None] = [None] * len(name_items)
    if len(ordinal_items) == len(name_items):
        try:
            paired = [int(item) for item in ordinal_items]
        except ValueError:
            paired = [None] * len(name_items)
    return [
        (position, ordinal, name)
        for position, (name, ordinal) in enumerate(zip(name_items, paired, strict=True), start=1)
    ]
