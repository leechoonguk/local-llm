"""Every derivation's row function against the table it writes.

A derived row is a dict handed to `LedgerStage`, which INSERTs exactly
`NATURAL_KEY + SYNCED_COLUMNS`. A key the model does not carry is silently
dropped; a column the function forgets is written NULL. Both are how a rename
goes wrong - measured 2026-09-14, when `permit_date` became `report_date` on
`food_item_report` and five product columns left the declaration table - so
the shape is asserted here, for all three kinds, before any pass runs.
"""

# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from app.models.food import item_report as report_model
from app.models.food import item_report_declaration as declaration_model
from app.models.food import item_report_ingredient as ingredient_model
from app.models.food import label as label_model
from app.models.food import safety_record as record_model
from app.services.food.item_report import _import_product, _report
from app.services.food.item_report_declaration import _declaration
from app.services.food.item_report_ingredient import _Registry, _split
from app.services.food.label_family import _import_label
from app.services.food.safety_record import _collection, _inspection, _recall


# ============================================================
# Constants
# ============================================================

# One ledger record wide enough to answer every column any of the three
# derivations reads off it.
IMPORT_RECORD = {
    "importer_name": "쏠트코리아",
    "product_name": "천일염",
    "product_name_en": "SEA SALT",
    "overseas_maker_name": "UBAIDIA",
    "origin_country": "파키스탄",
    "export_country": "파키스탄",
    "product_type_name": "천일염",
    "declaration_kind": "가공식품",
    "processed_date": "20260911",
    "expiry_text": "20180810 ~ 20280809",
    "expiry_from": "20180810",
    "expiry_to": "20280809",
    "label_text": "원재료명 : 천일염 보관방법 : 실온",
}

DOMESTIC_RECORD = {
    "item_report_no": "20130368349343",
    "license_no": "1955050900169",
    "business_name": "노벨유통",
    "permit_date": "20211209",
    "product_name": "찐빵",
    "product_type_name": "빵류",
    "shelf_life": "제조일로부터 1년",
}


# ============================================================
# Functions
# ============================================================


def _columns(model_module: object) -> set[str]:
    """What `LedgerStage` will INSERT for this table."""
    key: tuple[str, ...] = model_module.NATURAL_KEY  # type: ignore[attr-defined]
    synced: tuple[str, ...] = model_module.SYNCED_COLUMNS  # type: ignore[attr-defined]
    return set(key) | set(synced)


def test_a_report_row_is_exactly_the_report_table() -> None:
    """Both domestic kinds write every column of `food_item_report` and no other.

    The values are asserted too, because a shape alone survives a rename: a
    row function reading a column the ledger stopped carrying writes the right
    key with None in it.
    """
    for kind in (report_model.DOMESTIC_KIND, report_model.LIVESTOCK_KIND):
        row = _report(DOMESTIC_RECORD, kind)
        assert set(row) == _columns(report_model)
        assert row["report_date"] == "20211209"
        assert row["business_name"] == "노벨유통"
        assert row["maker_name"] == "노벨유통"
        assert row["origin_country"] == "대한민국"
        assert row["product_name_en"] is None


def test_an_import_product_row_is_exactly_the_report_table() -> None:
    """The import slice fills the same shape - what its registry omits is NULL, not absent."""
    row = _import_product("I0123456789abcdef", IMPORT_RECORD)
    assert set(row) == _columns(report_model)
    assert row["report_date"] == "20260911"
    assert row["maker_name"] == "UBAIDIA"
    assert row["product_name_en"] == "SEA SALT"
    assert row["license_no"] is None


def test_a_declaration_row_is_exactly_the_declaration_table() -> None:
    """And carries none of the product's own columns, which the edge reaches."""
    row = _declaration(IMPORT_RECORD)
    assert set(row) == _columns(declaration_model)
    assert "importer_name" not in row
    assert "expiry_text" not in row


def test_an_import_label_row_is_exactly_the_label_table() -> None:
    """One printed label writes the whole label shape, whatever the paragraph says."""
    assert set(_import_label(IMPORT_RECORD)) == _columns(label_model)


def test_an_ingredient_row_is_exactly_the_ingredient_table() -> None:
    """Each split name is a full row of `food_item_report_ingredient`."""
    record = {
        "item_report_no": "20130368349343",
        "raw_material_names": "정제수,설탕",
        "raw_material_ordinals": "1,2",
    }
    rows = _split(record, ingredient_model.DOMESTIC_KIND, _Registry([]))
    assert [set(row) for row in rows] == [_columns(ingredient_model)] * 2


def test_a_safety_record_row_is_exactly_the_record_table() -> None:
    """All three feeds write the same shape - what one feed never says is NULL."""
    recall = _recall(
        {
            "recall_disuse_seq": "3000234541",
            "item_report_no": "20130368349343",
            "product_name": "청인 해우",
            "recall_reason": "정부수거검사 부적합",
            "registered_at": "2026-09-14 17:19:13.501282",
        },
        {"20130368349343": "domestic"},
        {},
    )
    assert set(recall) == _columns(record_model)
    assert (recall["report_kind"], recall["recorded_on"]) == ("domestic", "20260914")
    assert recall["test_item_name"] is None

    inspection = _inspection(
        {
            "disposal_seq": "3000222960",
            "test_item_name": "프로사이미돈",
            "standard_text": "5.0 mg/kg 이하",
            "registered_on": "2026.03.11",
        },
        {},
        {},
    )
    assert set(inspection) == _columns(record_model)
    assert (inspection["report_kind"], inspection["recorded_on"]) == (None, "20260311")
    assert inspection["reason"] is None
    # 검사부적합 publishes only failures, so it writes the verdict it never sends.
    assert inspection["judgment"] == "부적합"

    collection = _collection(
        {
            "record_digest": "c" * 64,
            "item_report_no": "20130368349343",
            "product_name": "연돈카레",
            "collected_on": "20260825",
            "judgment": "적합",
            "plan_title": "민원관련 수거검사",
        },
        {"20130368349343": "domestic"},
    )
    assert set(collection) == _columns(record_model)
    assert (collection["report_kind"], collection["recorded_on"]) == ("domestic", "20260825")
    # A clean verdict is a record, which is the whole reason the table holds it.
    assert collection["judgment"] == "적합"
    assert collection["test_item_name"] is None
