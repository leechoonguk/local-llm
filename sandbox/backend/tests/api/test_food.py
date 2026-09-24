"""Food API tests — the read-only surface over the derived report table.

The rows come from the nightly derive job, never from a request, so the API
here is a window onto a table another process owns: paging, filtering, one
row with its edges, and the absence of every write verb.
"""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ServiceUnavailableError
from app.dependencies import core as deps_core
from app.models.food.business import FoodBusiness
from app.models.food.item_report import FoodItemReport
from app.models.food.item_report_declaration import FoodItemReportDeclaration
from app.models.food.item_report_ingredient import FoodItemReportIngredient
from app.models.food.label import FoodLabel
from app.models.food.label_allergen import FoodLabelAllergen
from app.models.food.label_caution import FoodLabelCaution
from app.models.food.label_packaging import FoodLabelPackaging
from app.models.food.nutrition import FoodNutrition
from app.models.food.product_classification import FoodProductClassification
from app.models.food.raw_material import FoodRawMaterial
from app.models.food.safety_record import FoodSafetyRecord
from app.schemas.food.chat import FoodChatTokenEvent
from app.services.food.chat import FoodChatService


async def _seed(*rows: object) -> None:
    """Rows the way the derive job leaves them - written into the client's own database.

    `client` swaps the session factory the app resolves, so the table the
    request reads is the one seeded here.
    """
    async with deps_core.async_session_factory() as session:
        session.add_all(rows)
        await session.commit()


def _report(kind: str, no: str, **columns: object) -> FoodItemReport:
    return FoodItemReport(report_kind=kind, item_report_no=no, **columns)


@pytest.mark.asyncio
async def test_list_item_reports_pages_with_a_total(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The footer's total counts the collection, not the page; the order is kind, then number."""
    await _seed(_report("livestock", "3"), _report("domestic", "2"), _report("domestic", "1"))

    page = client.get(
        "/api/v1/food/item-report/", params={"offset": 0, "limit": 2}, headers=auth_headers
    )
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert [(i["report_kind"], i["item_report_no"]) for i in body["items"]] == [
        ("domestic", "1"),
        ("domestic", "2"),
    ]
    assert all("version" in i for i in body["items"])


@pytest.mark.asyncio
async def test_list_item_reports_filters_narrow_the_total_too(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A filtered list and its total agree; text fields match a fragment, kind and type whole."""
    await _seed(
        _report("domestic", "1", product_name="찐빵", product_type_name="빵류"),
        _report("domestic", "2", product_name="단팥빵", product_type_name="빵류"),
        _report("livestock", "3", product_name="빵 소시지", product_type_name="소시지"),
    )

    by_name = client.get(
        "/api/v1/food/item-report/", params={"product_name": "빵"}, headers=auth_headers
    )
    assert by_name.json()["total"] == 3
    by_kind = client.get(
        "/api/v1/food/item-report/",
        params={"product_name": "빵", "report_kind": "domestic"},
        headers=auth_headers,
    )
    assert by_kind.json()["total"] == 2
    assert [i["item_report_no"] for i in by_kind.json()["items"]] == ["1", "2"]
    whole = client.get(
        "/api/v1/food/item-report/", params={"product_type_name": "빵류"}, headers=auth_headers
    )
    assert whole.json()["total"] == 2
    # The type is picked from the facets, so a fragment of a name is not that name.
    fragment = client.get(
        "/api/v1/food/item-report/", params={"product_type_name": "빵"}, headers=auth_headers
    )
    assert fragment.json()["total"] == 0


@pytest.mark.asyncio
async def test_item_report_facets_are_the_rows_own_type_names(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The 식품유형 select's options: every name the table holds, once, sorted, NULL left out."""
    await _seed(
        _report("domestic", "1", product_type_name="빵류"),
        _report("domestic", "2", product_type_name="소시지"),
        _report("livestock", "3", product_type_name="빵류"),
        _report("livestock", "4"),
    )

    facets = client.get("/api/v1/food/item-report/facets", headers=auth_headers)
    assert facets.status_code == 200
    assert facets.json() == {"product_type_name": ["빵류", "소시지"]}
    assert client.get("/api/v1/food/item-report/facets").status_code == 401


@pytest.mark.asyncio
async def test_get_item_report_carries_its_edges(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """One report answers with its label in order and its nutrition."""
    await _seed(
        _report("domestic", "1", product_name="찐빵", product_type_name="빵류"),
        FoodProductClassification(
            product_code="C0301040000000", korean_name="빵류", product_yn="Y", level="4"
        ),
        FoodItemReportIngredient(
            report_kind="domestic", item_report_no="1", position=2, name="설탕"
        ),
        FoodItemReportIngredient(
            report_kind="domestic", item_report_no="1", position=1, ordinal=1, name="밀가루"
        ),
        FoodItemReportIngredient(
            report_kind="livestock", item_report_no="1", position=1, name="돼지고기"
        ),
        FoodNutrition(
            food_code="D1",
            food_name="찐빵",
            report_kind="domestic",
            item_report_no="1",
            energy_kcal=250,
        ),
    )
    listed = client.get("/api/v1/food/item-report/", headers=auth_headers).json()["items"]

    detail = client.get(f"/api/v1/food/item-report/{listed[0]['id']}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert [(i["position"], i["ordinal"], i["name"]) for i in body["ingredients"]] == [
        (1, 1, "밀가루"),
        (2, None, "설탕"),
    ]
    nutrition = [(n["food_code"], float(n["energy_kcal"])) for n in body["nutritions"]]
    assert nutrition == [("D1", 250.0)]


@pytest.mark.asyncio
async def test_an_import_product_answers_its_declarations_newest_first(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The product row states how often it was declared; the rows are their own paged route.

    A product is declared 3.6 times on average and 1,388 times at the widest
    (2026-09-14), which is why the count is on the product and the crossings
    are a page - and why a domestic product, whose registry publishes no
    declarations, answers 0 and an empty page rather than nothing.
    """
    await _seed(
        _report("import", "I1", product_name="천일염"),
        _report("domestic", "1", product_name="찐빵"),
        FoodItemReportDeclaration(
            report_kind="import",
            declaration_key="D1",
            item_report_no="I1",
            declaration_kind="가공식품",
            export_country="파키스탄",
            processed_date="20200508",
            expiry_from="20180810",
            expiry_to="20280809",
        ),
        FoodItemReportDeclaration(
            report_kind="import",
            declaration_key="D2",
            item_report_no="I1",
            declaration_kind="가공식품",
            export_country="중국",
            processed_date="20260911",
        ),
        # The recall sat on the first lot: the page says so beside that row,
        # and nothing beside the other.
        FoodSafetyRecord(
            record_key="R0123456789abcdef",
            record_kind="recall",
            report_kind="import",
            item_report_no="I1",
            recorded_on="20260914",
            lot_date="20180810",
            grade="2등급",
        ),
    )
    listed = client.get("/api/v1/food/item-report/", headers=auth_headers).json()["items"]
    by_number = {row["item_report_no"]: row["id"] for row in listed}

    detail = client.get(f"/api/v1/food/item-report/{by_number['I1']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["declaration_count"] == 2

    page = client.get(
        f"/api/v1/food/item-report/{by_number['I1']}/declarations", headers=auth_headers
    )
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 2
    assert [row["processed_date"] for row in body["items"]] == ["20260911", "20200508"]
    assert body["items"][1]["expiry_to"] == "20280809"
    assert [
        (row["record_count"], row["failed_record_count"], row["recall_grade"])
        for row in body["items"]
    ] == [(0, 0, None), (1, 0, "2등급")]

    domestic = client.get(f"/api/v1/food/item-report/{by_number['1']}", headers=auth_headers)
    assert domestic.json()["declaration_count"] == 0
    empty = client.get(
        f"/api/v1/food/item-report/{by_number['1']}/declarations", headers=auth_headers
    )
    assert empty.json() == {"items": [], "total": 0}


@pytest.mark.asyncio
async def test_a_product_answers_the_events_published_about_it(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A recall and a failed inspection hang off the product, newest first.

    The count rides on the detail because it is one number; the rows are their
    own paged route, like the declarations beside them.
    """
    await _seed(
        _report("domestic", "1", product_name="찐빵"),
        FoodSafetyRecord(
            record_key="R0123456789abcdef",
            record_kind="recall",
            report_kind="domestic",
            item_report_no="1",
            recorded_on="20260914",
            reason="정부수거검사 부적합",
            grade="3등급",
        ),
        FoodSafetyRecord(
            record_key="F0123456789abcdef",
            record_kind="inspection_failure",
            report_kind="domestic",
            item_report_no="1",
            recorded_on="20260311",
            test_item_name="프로사이미돈",
            test_result_text="20.2 mg/kg",
        ),
    )
    listed = client.get("/api/v1/food/item-report/", headers=auth_headers).json()["items"]
    report_id = listed[0]["id"]

    detail = client.get(f"/api/v1/food/item-report/{report_id}", headers=auth_headers)
    # The detail still counts, because the product's own screen shows its
    # events when it has any - it is counted at read time, never stored.
    assert detail.json()["record_count"] == 2

    page = client.get(f"/api/v1/food/item-report/{report_id}/safety-records", headers=auth_headers)
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 2
    assert [row["record_kind"] for row in body["items"]] == ["recall", "inspection_failure"]
    assert body["items"][0]["grade"] == "3등급"
    assert body["items"][1]["test_result_text"] == "20.2 mg/kg"


@pytest.mark.asyncio
async def test_events_are_a_list_of_their_own_with_its_own_narrowing(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """946 events over 1.9M products (2026-09-14): a screen of their own, not a product column.

    An event is an authority's action, so it is read by date and kind across
    every product - and the selects offer what the feeds actually published.
    """
    await _seed(
        _report("domestic", "1", product_name="찐빵"),
        _report("domestic", "2", product_name="몽고간장"),
        FoodSafetyRecord(
            record_key="R1",
            record_kind="recall",
            report_kind="domestic",
            item_report_no="2",
            product_name="몽고간장 국",
            business_name="몽고식품",
            recorded_on="20260610",
            grade="3등급",
        ),
        FoodSafetyRecord(
            record_key="F1",
            record_kind="inspection_failure",
            report_kind="domestic",
            item_report_no="2",
            product_name="몽고간장 국",
            recorded_on="20250311",
        ),
    )

    page = client.get("/api/v1/food/safety-record/", headers=auth_headers).json()
    assert [row["record_key"] for row in page["items"]] == ["R1", "F1"]
    assert page["total"] == 2
    assert page["items"][0]["product_name"] == "몽고간장 국"

    recalls = client.get(
        "/api/v1/food/safety-record/",
        params={"record_kind": "recall", "record_year": "2026"},
        headers=auth_headers,
    ).json()
    assert [row["record_key"] for row in recalls["items"]] == ["R1"]

    ranged = client.get(
        "/api/v1/food/safety-record/",
        params={"recorded_on_from": "20250101", "recorded_on_to": "20251231"},
        headers=auth_headers,
    ).json()
    assert [row["record_key"] for row in ranged["items"]] == ["F1"]

    named = client.get(
        "/api/v1/food/safety-record/",
        params={"business_name": "몽고"},
        headers=auth_headers,
    ).json()
    assert named["total"] == 1

    facets = client.get("/api/v1/food/safety-record/facets", headers=auth_headers).json()
    assert facets == {
        "record_kind": ["inspection_failure", "recall"],
        "judgment_code": [],
        "report_kind": ["domestic"],
        "record_year": ["2026", "2025"],
    }


@pytest.mark.asyncio
async def test_item_report_missing_row_and_write_verbs(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A derived table answers 404 for a row it does not hold and has no write verb."""
    missing = client.get(f"/api/v1/food/item-report/{uuid4()}", headers=auth_headers)
    assert missing.status_code == 404
    posted = client.post("/api/v1/food/item-report/", json={}, headers=auth_headers)
    assert posted.status_code == 405
    assert client.get("/api/v1/food/item-report/").status_code == 401


@pytest.mark.asyncio
async def test_get_item_report_standards_answers_per_type(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """One entry per type the report names, path included; a report naming none answers none."""
    await _seed(
        _report("domestic", "1", product_type_name="빵류"),
        _report("domestic", "2", product_type_name="없는유형"),
        FoodProductClassification(
            product_code="C0000000000000", korean_name="가공식품", product_yn="N", level="1"
        ),
        FoodProductClassification(
            product_code="C0301040000000",
            korean_name="빵류",
            product_yn="Y",
            level="4",
            parent_product_code="C0000000000000",
        ),
    )
    listed = client.get("/api/v1/food/item-report/", headers=auth_headers).json()["items"]

    standards = client.get(
        f"/api/v1/food/item-report/{listed[0]['id']}/standards", headers=auth_headers
    )
    assert standards.status_code == 200
    (entry,) = standards.json()["types"]
    assert entry["node"]["korean_name"] == "빵류"
    assert [n["korean_name"] for n in entry["path"]] == ["가공식품", "빵류"]
    assert entry["individual_standards"] == [] and entry["common_standards"] == []
    untyped = client.get(
        f"/api/v1/food/item-report/{listed[1]['id']}/standards", headers=auth_headers
    )
    assert untyped.json() == {"types": []}
    missing = client.get(f"/api/v1/food/item-report/{uuid4()}/standards", headers=auth_headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_get_item_report_labels_answers_both_portals(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Every printed label of the report, 푸드QR first; a report with none answers an empty list."""
    await _seed(
        _report("domestic", "1", product_name="대추차플러스"),
        _report("domestic", "2", product_name="라벨없는제품"),
        FoodLabel(
            source="food-qr",
            label_key="202410221000001856",
            item_report_no="1",
            product_name="대추차플러스",
            barcode_no="08801007901244",
            content_amount_text="15g (60kcal)",
            storage_text="직사광선을 피해 보관",
            raw_material_text="대추농축액, 정제수",
        ),
        FoodLabel(
            source="haccp",
            label_key="1",
            item_report_no="1",
            product_name="대추차플러스 스틱",
            content_amount_text="15g*20",
            maker_name="담터",
        ),
        FoodLabelAllergen(
            source="food-qr", label_key="202410221000001856", position=1, name="대두"
        ),
        FoodLabelCaution(
            source="food-qr",
            label_key="202410221000001856",
            position=1,
            caution_text="부정·불량식품신고는 국번없이 1399",
        ),
        FoodLabelPackaging(
            source="food-qr",
            label_key="202410221000001856",
            position=1,
            packaging_text="(내면) 폴리프로필렌",
        ),
    )
    listed = client.get("/api/v1/food/item-report/", headers=auth_headers).json()["items"]

    labelled = client.get(
        f"/api/v1/food/item-report/{listed[0]['id']}/labels", headers=auth_headers
    )
    assert labelled.status_code == 200
    labels = labelled.json()["labels"]
    assert [(label["source"], label["content_amount_text"]) for label in labels] == [
        ("food-qr", "15g (60kcal)"),
        ("haccp", "15g*20"),
    ]
    assert labels[0]["storage_text"] == "직사광선을 피해 보관"
    assert labels[0]["raw_material_text"] == "대추농축액, 정제수"
    assert [a["name"] for a in labels[0]["allergens"]] == ["대두"]
    cautions = [c["caution_text"] for c in labels[0]["cautions"]]
    assert cautions == ["부정·불량식품신고는 국번없이 1399"]
    packagings = [p["packaging_text"] for p in labels[0]["packagings"]]
    assert packagings == ["(내면) 폴리프로필렌"]
    # The HACCP portal publishes none of the three, and says so with empty lists.
    empty = (labels[1]["allergens"], labels[1]["cautions"], labels[1]["packagings"])
    assert empty == ([], [], [])
    assert labels[1]["maker_name"] == "담터"

    unlabelled = client.get(
        f"/api/v1/food/item-report/{listed[1]['id']}/labels", headers=auth_headers
    )
    assert unlabelled.json() == {"labels": []}
    missing = client.get(f"/api/v1/food/item-report/{uuid4()}/labels", headers=auth_headers)
    assert missing.status_code == 404


def _material(code: str, name: str, **columns: object) -> FoodRawMaterial:
    return FoodRawMaterial(
        raw_material_code=code, base_code=code[:8], representative_raw_material_name=name, **columns
    )


@pytest.mark.asyncio
async def test_list_raw_materials_filters_narrow_the_total_too(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A fragment on the name, a whole value on the class, and a total that agrees with both."""
    await _seed(
        _material("A1000911010001", "밀가루", raw_material_medium_class="식물"),
        _material("A1000911280000", "밀기울", raw_material_medium_class="식물", use_yn="N"),
        _material("A1000912010001", "밀배아", raw_material_medium_class="식물성유지"),
    )

    page = client.get(
        "/api/v1/food/raw-material/",
        params={"offset": 0, "limit": 20, "representative_raw_material_name": "밀"},
        headers=auth_headers,
    )
    assert page.status_code == 200
    assert page.json()["total"] == 3
    narrowed = client.get(
        "/api/v1/food/raw-material/",
        params={"offset": 0, "limit": 1, "raw_material_medium_class": "식물"},
        headers=auth_headers,
    )
    body = narrowed.json()
    assert body["total"] == 2
    assert [i["raw_material_code"] for i in body["items"]] == ["A1000911010001"]
    retired = client.get("/api/v1/food/raw-material/", params={"use_yn": "N"}, headers=auth_headers)
    assert [i["raw_material_code"] for i in retired.json()["items"]] == ["A1000911280000"]
    outside = client.get("/api/v1/food/raw-material/", params={"use_yn": "X"}, headers=auth_headers)
    assert outside.status_code == 422
    assert client.get("/api/v1/food/raw-material/").status_code == 401


@pytest.mark.asyncio
async def test_raw_material_facets_and_detail_with_its_variants(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The facets are the rows' values; the detail carries every code of the base."""
    await _seed(
        _material(
            "A1000911010001",
            "밀가루",
            raw_material_large_class="식품원료(A코드)",
            raw_material_medium_class="식물",
        ),
        _material("A1000911280000", "밀기울", raw_material_large_class="식품원료(A코드)"),
    )

    facets = client.get("/api/v1/food/raw-material/facets", headers=auth_headers)
    assert facets.status_code == 200
    assert facets.json()["raw_material_medium_class_by_large"] == {"식품원료(A코드)": ["식물"]}

    first = client.get("/api/v1/food/raw-material/", headers=auth_headers).json()["items"][0]
    detail = client.get(f"/api/v1/food/raw-material/{first['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert [v["raw_material_code"] for v in detail.json()["variants"]] == [
        "A1000911010001",
        "A1000911280000",
    ]
    missing = client.get(f"/api/v1/food/raw-material/{uuid4()}", headers=auth_headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_raw_material_item_reports_page_with_a_total(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The products behind a material page like every collection; a missing material is 404."""
    await _seed(
        _material("A1000911010001", "밀가루"),
        _report("domestic", "1", product_name="찐빵"),
        _report("domestic", "2", product_name="식빵"),
        FoodItemReportIngredient(
            report_kind="domestic",
            item_report_no="1",
            position=1,
            name="밀가루",
            material_code="A1000911010001",
        ),
        FoodItemReportIngredient(
            report_kind="domestic",
            item_report_no="2",
            position=1,
            name="밀가루",
            material_code="A1000911010001",
        ),
    )
    flour = client.get("/api/v1/food/raw-material/", headers=auth_headers).json()["items"][0]

    page = client.get(
        f"/api/v1/food/raw-material/{flour['id']}/item-reports",
        params={"offset": 0, "limit": 1},
        headers=auth_headers,
    )
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 2
    assert [i["product_name"] for i in body["items"]] == ["찐빵"]
    missing = client.get(f"/api/v1/food/raw-material/{uuid4()}/item-reports", headers=auth_headers)
    assert missing.status_code == 404


MEAT = "식육포장처리업"


def _business(license_no: str, name: str, **columns: object) -> FoodBusiness:
    columns.setdefault("status", "ACTIVE")
    columns.setdefault("industry_name", "식품제조가공업")
    return FoodBusiness(license_no=license_no, business_name=name, name_key=name, **columns)


@pytest.mark.asyncio
async def test_list_businesses_filters_narrow_the_total_too(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A fragment on the name, a whole value on industry and status, and a total that agrees."""
    await _seed(
        _business("20060169056", "금정상사", district="대구광역시 북구"),
        _business("20140257670", "솔티마을", district="세종특별자치시", industry_name=MEAT),
        _business("18760461001", "삼립웰가", status="CLOSED", closed_date="20070130"),
    )

    page = client.get("/api/v1/food/business/", params={"limit": 20}, headers=auth_headers)
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert [b["license_no"] for b in page.json()["items"]] == [
        "18760461001",
        "20060169056",
        "20140257670",
    ]
    live = client.get("/api/v1/food/business/", params={"status": "ACTIVE"}, headers=auth_headers)
    assert live.json()["total"] == 2
    meat = client.get(
        "/api/v1/food/business/",
        params={"industry_name": "식육포장처리업", "business_name": "솔티"},
        headers=auth_headers,
    )
    assert [b["business_name"] for b in meat.json()["items"]] == ["솔티마을"]
    outside = client.get("/api/v1/food/business/", params={"status": "OPEN"}, headers=auth_headers)
    assert outside.status_code == 422
    assert client.get("/api/v1/food/business/").status_code == 401


@pytest.mark.asyncio
async def test_business_facets_and_detail_with_its_namesakes_and_neighbours(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The facets are the rows' industries; the detail lists its namesakes and its neighbours.

    Neither list includes the row itself, and a row with no site key has no neighbours.
    """
    await _seed(
        _business("1", "우리식품", district="부산광역시 사하구", site_key="BLD-1"),
        _business("2", "우리식품", district="경상남도 김해시", status="CLOSED"),
        _business(
            "3", "다른식품", district="부산광역시 사하구", site_key="BLD-1", industry_name=MEAT
        ),
        _business("4", "외딴식품"),
    )

    facets = client.get("/api/v1/food/business/facets", headers=auth_headers)
    assert facets.status_code == 200
    assert facets.json()["industry_name"] == ["식육포장처리업", "식품제조가공업"]

    rows = client.get("/api/v1/food/business/", headers=auth_headers).json()["items"]
    by_licence = {row["license_no"]: row for row in rows}
    detail = client.get(f"/api/v1/food/business/{by_licence['1']['id']}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert [b["license_no"] for b in body["same_name"]] == ["2"]
    assert [b["license_no"] for b in body["same_site"]] == ["3"]

    lonely_url = f"/api/v1/food/business/{by_licence['4']['id']}"
    lonely = client.get(lonely_url, headers=auth_headers).json()
    assert (lonely["same_name"], lonely["same_site"]) == ([], [])
    missing = client.get(f"/api/v1/food/business/{uuid4()}", headers=auth_headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_chat_streams_tokens_then_one_end(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The turn arrives as events: many `token`, exactly one `end` carrying the whole answer."""
    with client.stream(
        "POST",
        "/api/v1/food/chat",
        json={"message": "밀가루"},
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [
            line.removeprefix("event: ")
            for line in response.iter_lines()
            if line.startswith("event: ")
        ]

    assert events.count("end") == 1
    assert events[-1] == "end"
    assert events.count("token") == len(events) - 1
    assert events.count("token") > 1


@pytest.mark.asyncio
async def test_chat_refuses_a_turn_with_nothing_in_it(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An empty message is a 422 at the boundary, and the stream is never opened."""
    empty = client.post("/api/v1/food/chat", json={"message": ""}, headers=auth_headers)
    assert empty.status_code == 422
    assert client.post("/api/v1/food/chat", json={"message": "밀"}).status_code == 401


@pytest.mark.asyncio
async def test_chat_says_a_failure_inside_the_stream(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answerer being down is an `error` event, not a dropped connection.

    By then the 200 status line is long gone, so a stream that simply stopped
    would read as a lost network and the screen would keep half an answer as
    if it were the whole one.
    """

    async def _down(self: FoodChatService, message: str) -> AsyncIterator[FoodChatTokenEvent]:
        yield FoodChatTokenEvent(text="답")
        raise ServiceUnavailableError("the answerer is down")

    monkeypatch.setattr(FoodChatService, "answer", _down)

    with client.stream(
        "POST", "/api/v1/food/chat", json={"message": "밀"}, headers=auth_headers
    ) as response:
        assert response.status_code == 200
        lines = [line for line in response.iter_lines() if line != ""]

    names = [line for line in lines if line.startswith("event: ")]
    assert names == ["event: token", "event: error"]
    assert '"code":"service_unavailable"' in "".join(lines).replace(" ", "")
