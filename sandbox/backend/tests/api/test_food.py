"""Food API tests — the read-only ledger surface.

The rows come from a nightly sync, never from a request, so the API here is a
window onto a table another process owns: paging, filtering, one row by id, and
the absence of every write verb.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import core as deps_core
from app.schemas.food.raw_material import FoodRawMaterialCreateRequest
from app.services.food.raw_material import FoodRawMaterialService


async def _seed(*codes: tuple[str, str]) -> None:
    """Rows the way the sync writes them — through the service, as the batch actor.

    Written into the client's own database: `client` swaps the session factory
    the app resolves, so the ledger the request reads is the one seeded here.
    """
    async with deps_core.async_session_factory() as session:
        service = FoodRawMaterialService(session)
        for code, name in codes:
            await service.create_raw_material(
                FoodRawMaterialCreateRequest(
                    raw_material_code=code, representative_raw_material_name=name
                ),
                created_by="batch:sync_food_raw_material_ledger",
            )


@pytest.mark.asyncio
async def test_list_raw_materials_pages_with_a_total(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The footer's total counts the collection, not the page."""
    await _seed(("A1", "고춧가루"), ("A2", "마늘"), ("A3", "생강"))

    page = client.get(
        "/api/v1/food/raw-material/", params={"offset": 0, "limit": 2}, headers=auth_headers
    )
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert [i["raw_material_code"] for i in body["items"]] == ["A1", "A2"]
    assert all("version" in i for i in body["items"])


@pytest.mark.asyncio
async def test_list_raw_materials_filters_narrow_the_total_too(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A filtered list and its total must agree — "1-1 of 3" on one matching row is a lie."""
    await _seed(("A1", "고추가루"), ("A2", "마늘"), ("B1", "고추장"))

    by_code = client.get(
        "/api/v1/food/raw-material/", params={"raw_material_code": "a"}, headers=auth_headers
    )
    assert by_code.json()["total"] == 2

    by_name = client.get(
        "/api/v1/food/raw-material/",
        params={"representative_raw_material_name": "고추"},
        headers=auth_headers,
    )
    assert [i["raw_material_code"] for i in by_name.json()["items"]] == ["A1", "B1"]
    assert by_name.json()["total"] == 2

    both = client.get(
        "/api/v1/food/raw-material/",
        params={"raw_material_code": "B", "representative_raw_material_name": "고추"},
        headers=auth_headers,
    )
    assert [i["raw_material_code"] for i in both.json()["items"]] == ["B1"]


@pytest.mark.asyncio
async def test_select_filters_match_whole_values_and_offer_the_ledgers_own(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A picked value matches whole: `식물` must not return `식물성유지`.

    And what can be picked is what the rows hold: the facets are read from the
    ledger, sorted, NULL left out - a value typed into a fixed list would offer
    yesterday's vocabulary the night the portal adds one.
    """
    async with deps_core.async_session_factory() as session:
        service = FoodRawMaterialService(session)
        rows = (("A1", "식물", "가루"), ("A2", "식물성유지", None), ("A3", "동물", "가루"))
        for code, large, status in rows:
            await service.create_raw_material(
                FoodRawMaterialCreateRequest(
                    raw_material_code=code,
                    raw_material_large_class=large,
                    raw_material_status_code_name=status,
                ),
                created_by="batch:sync_food_raw_material_ledger",
            )

    exact = client.get(
        "/api/v1/food/raw-material/",
        params={"raw_material_large_class": "식물"},
        headers=auth_headers,
    )
    assert [i["raw_material_code"] for i in exact.json()["items"]] == ["A1"]
    assert exact.json()["total"] == 1

    facets = client.get("/api/v1/food/raw-material/facets", headers=auth_headers)
    assert facets.status_code == 200
    assert facets.json()["raw_material_large_class"] == ["동물", "식물", "식물성유지"]
    assert facets.json()["raw_material_status_code_name"] == ["가루"]
    assert facets.json()["raw_material_medium_class"] == []
    assert facets.json()["raw_material_medium_class_by_large"] == {}


def test_raw_materials_require_auth(client: TestClient) -> None:
    """The ledger is behind the same door as everything else."""
    assert client.get("/api/v1/food/raw-material/").status_code == 401


def test_the_ledger_has_no_write_verbs(client: TestClient, auth_headers: dict[str, str]) -> None:
    """A row written here would be overwritten by the next sync — so it cannot be written here.

    POST answers 405: the collection path exists for GET and the method is what is
    refused. PATCH and DELETE answer 404, because no by-id path exists at all - the
    grid is the whole screen, so nothing is published by id.
    """
    assert (
        client.post("/api/v1/food/raw-material/", json={}, headers=auth_headers).status_code == 405
    )
    some_id = uuid4()
    assert (
        client.patch(
            f"/api/v1/food/raw-material/{some_id}", json={}, headers=auth_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/food/raw-material/{some_id}", headers=auth_headers).status_code
        == 404
    )
