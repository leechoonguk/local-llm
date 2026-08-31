"""Integration configuration API: CRUD, execute, and secret sub-collection."""

from __future__ import annotations

from typing import cast

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.repositories.integration.provider import IntegrationProviderRepository


def integration_payload() -> dict[str, object]:
    """A complete provider as an operator would post it.

    Every field location appears once, so a test can break exactly one of them
    and still send an otherwise valid document.
    """
    return {
        "code": "freshplate",
        "display_name": "FreshPlate Partner API",
        "base_url": "https://partner-api.freshplate.example",
        "secrets": [
            {
                "name": "partner-api-key",
                "value": "issued-key",
                "description": "FreshPlate partner key",
            }
        ],
        "operations": [
            {
                "code": "lookup-menu-item",
                "method": "GET",
                "path_template": "/v1/menus/{menu_id}/items/{menu_item_id}",
                "connect_timeout_ms": 100,
                "read_timeout_ms": 200,
                "max_retries": 1,
                "retry_base_ms": 10,
                "retry_max_ms": 20,
                "idempotent": True,
                "fields": [
                    {
                        "direction": "REQUEST",
                        "location": "PATH",
                        "key": "menu_id",
                        "wire_path": "menu_id",
                        "value_source": "CALLER",
                        "value_type": "STRING",
                        "required": True,
                    },
                    {
                        "direction": "REQUEST",
                        "location": "PATH",
                        "key": "menu_item_id",
                        "wire_path": "menu_item_id",
                        "value_source": "CALLER",
                        "value_type": "STRING",
                        "required": True,
                        "ordinal": 1,
                    },
                    {
                        "direction": "REQUEST",
                        "location": "QUERY",
                        "key": "include_unavailable",
                        "wire_path": "include_unavailable",
                        "value_source": "CALLER",
                        "value": None,
                        "value_type": "BOOLEAN",
                        "required": False,
                        "ordinal": 2,
                    },
                    {
                        "direction": "REQUEST",
                        "location": "HEADER",
                        "key": "partner_api_key",
                        "wire_path": "x-api-key",
                        "value_source": "SECRET",
                        "secret_name": "partner-api-key",
                        "value_type": "STRING",
                        "required": True,
                        "sensitive": True,
                        "ordinal": 3,
                    },
                    {
                        "direction": "RESPONSE",
                        "location": "HEADER",
                        "key": "rate_limit_remaining",
                        "wire_path": "x-rate-limit-remaining",
                        "match_mode": "PRESENT",
                        "value_type": "INTEGER",
                        "required": False,
                    },
                    {
                        "direction": "RESPONSE",
                        "location": "BODY",
                        "key": "menu_item_id",
                        "wire_path": "/data/id",
                        "value_type": "STRING",
                        "required": True,
                    },
                    {
                        "direction": "RESPONSE",
                        "location": "BODY",
                        "key": "menu_item_name",
                        "wire_path": "/data/name",
                        "value_type": "STRING",
                        "required": True,
                        "ordinal": 1,
                    },
                    {
                        "direction": "RESPONSE",
                        "location": "BODY",
                        "key": "price",
                        "wire_path": "/data/price",
                        "value_type": "NUMBER",
                        "required": True,
                        "ordinal": 2,
                    },
                    {
                        "direction": "RESPONSE",
                        "location": "BODY",
                        "key": "available",
                        "wire_path": "/data/available",
                        "value_type": "BOOLEAN",
                        "required": True,
                        "ordinal": 3,
                    },
                ],
            }
        ],
    }


def test_integration_configuration_crud(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Stored configuration round-trips, and no response ever echoes a secret.

    The value is write-only by design: an operator posts it once, and every
    later read shows the name only.
    """
    created = client.post("/api/v1/integration/", json=integration_payload(), headers=auth_headers)
    assert created.status_code == 201
    body = created.json()
    integration_id = body["id"]
    assert body["operations"][0]["code"] == "lookup-menu-item"
    secret_field = body["operations"][0]["fields"][3]
    assert secret_field["value_source"] == "SECRET"
    # The field names its secret; the value lives in integration_secret and is never echoed.
    assert secret_field["secret_name"] == "partner-api-key"
    assert "value" not in body["secrets"][0]
    assert body["secrets"][0]["name"] == "partner-api-key"

    listed = client.get("/api/v1/integration/", headers=auth_headers)
    assert listed.status_code == 200
    listed_body = listed.json()
    assert [row["code"] for row in listed_body] == ["freshplate"]
    assert "value" not in listed_body[0]["secrets"][0]

    fetched = client.get(f"/api/v1/integration/{integration_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == integration_id

    updated = client.patch(
        f"/api/v1/integration/{integration_id}",
        json={"display_name": "FreshPlate Partner API v2", "operations": []},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "FreshPlate Partner API v2"
    assert updated.json()["operations"] == []

    deleted = client.delete(f"/api/v1/integration/{integration_id}", headers=auth_headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    assert (
        client.get(f"/api/v1/integration/{integration_id}", headers=auth_headers).status_code == 404
    )


def test_integration_configuration_rejects_invalid_values(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Plain HTTP and a caller-set `authorization` header are both refused.

    Both would be stored and then trusted by the transport — one sends
    credentials in clear text, the other lets configuration forge auth.

    The codes differ on purpose: a form can point at the `base_url` input for
    the first, while the second is a field-level mistake with no input of its
    own, so it carries the generic configuration code.
    """
    invalid_url = integration_payload()
    invalid_url["base_url"] = "http://partner-api.freshplate.example"
    response = client.post("/api/v1/integration/", json=invalid_url, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["code"] == "provider_base_url_invalid"

    invalid_header = integration_payload()
    operations = invalid_header["operations"]
    assert isinstance(operations, list)
    operation = operations[0]
    assert isinstance(operation, dict)
    operation["fields"] = [
        {
            "direction": "REQUEST",
            "location": "HEADER",
            "key": "authorization",
            "wire_path": "authorization",
            "value_source": "LITERAL",
            "value": "unsafe",
            "value_type": "STRING",
            "required": True,
        }
    ]
    response = client.post("/api/v1/integration/", json=invalid_header, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["code"] == "integration_configuration_invalid"


def test_integration_execute_operation_returns_canonical_result(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A configured provider is callable end to end, with no code change.

    The handler asserts the rendered path, query and secret header, and the
    response is reduced to the caller-facing keys the configuration names —
    that reduction is the whole product of this API.
    """
    created = client.post("/api/v1/integration/", json=integration_payload(), headers=auth_headers)
    assert created.status_code == 201
    integration_id = created.json()["id"]

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/menus/menu-1/items/item-1"
        assert request.url.params["include_unavailable"] == "False"
        assert request.headers["x-api-key"] == "issued-key"
        return httpx2.Response(
            200,
            headers={"x-rate-limit-remaining": "42"},
            json={
                "data": {
                    "id": "item-1",
                    "name": "Tea",
                    "price": 3.5,
                    "available": True,
                }
            },
        )

    app = cast(FastAPI, client.app)
    app.state.integration_http_client._transport = httpx2.MockTransport(handler)
    response = client.post(
        f"/api/v1/integration/{integration_id}/operations/lookup-menu-item/execute",
        json={
            "inputs": {
                "menu_id": "menu-1",
                "menu_item_id": "item-1",
                # A CALLER field has no default: unsent means unsent, so the
                # query parameter only appears because the caller states it.
                "include_unavailable": False,
            }
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "canonical_payload": {
            "menu_item_id": "item-1",
            "menu_item_name": "Tea",
            "price": 3.5,
            "available": True,
        },
        "metadata": {"rate_limit_remaining": 42},
        "status_code": 200,
    }


def test_integration_execute_operation_maps_external_errors(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A provider 500 becomes 502 naming the provider and operation.

    Answering 500 would blame this service for someone else's outage, and
    without the names an on-call reader cannot tell which provider failed.
    """
    created = client.post("/api/v1/integration/", json=integration_payload(), headers=auth_headers)
    assert created.status_code == 201
    integration_id = created.json()["id"]

    app = cast(FastAPI, client.app)
    app.state.integration_http_client._transport = httpx2.MockTransport(
        lambda request: httpx2.Response(500, json={})
    )
    response = client.post(
        f"/api/v1/integration/{integration_id}/operations/lookup-menu-item/execute",
        json={"inputs": {"menu_id": "menu-1", "menu_item_id": "item-1"}},
        headers=auth_headers,
    )
    assert response.status_code == 502
    assert response.json()["code"] == "integration_error"
    assert response.json()["provider"] == "freshplate"
    assert response.json()["operation"] == "lookup-menu-item"


def test_integration_execute_operation_unknown_operation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown operation on a known provider is 422, not 404.

    The provider exists, so the fix is configuration; 404 would send the
    caller looking for a missing row.
    """
    created = client.post("/api/v1/integration/", json=integration_payload(), headers=auth_headers)
    assert created.status_code == 201
    integration_id = created.json()["id"]

    response = client.post(
        f"/api/v1/integration/{integration_id}/operations/missing/execute",
        json={"inputs": {}},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "integration_configuration_invalid"


def test_integration_execute_operation_missing_required_input(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An omitted required CALLER input is 422 `integration_input_invalid`.

    Its own code, not the configuration one: the configuration is fine and
    nothing upstream was called — the caller has to send the field. A CALLER
    field carries no default, so omission cannot silently become a value.
    """
    created = client.post("/api/v1/integration/", json=integration_payload(), headers=auth_headers)
    assert created.status_code == 201
    integration_id = created.json()["id"]

    response = client.post(
        f"/api/v1/integration/{integration_id}/operations/lookup-menu-item/execute",
        json={"inputs": {"menu_item_id": "item-1"}},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "integration_input_invalid"
    assert "menu_id" in response.json()["detail"]


def test_integration_execute_operation_unknown_provider(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown provider id is 404 — the execute path is still id-scoped."""
    response = client.post(
        "/api/v1/integration/00000000-0000-0000-0000-000000000000/operations/lookup/execute",
        json={"inputs": {}},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_integration_secret_endpoints(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Secrets are created, listed without their value, and protected while referenced."""
    created = client.post("/api/v1/integration/", json=integration_payload(), headers=auth_headers)
    assert created.status_code == 201
    integration_id = created.json()["id"]

    added = client.post(
        f"/api/v1/integration/{integration_id}/secrets",
        json={"name": "reporting-key", "value": "second-key"},
        headers=auth_headers,
    )
    assert added.status_code == 201
    assert added.json()["name"] == "reporting-key"
    assert "value" not in added.json()

    duplicate = client.post(
        f"/api/v1/integration/{integration_id}/secrets",
        json={"name": "reporting-key", "value": "again"},
        headers=auth_headers,
    )
    assert duplicate.status_code == 409

    listed = client.get(f"/api/v1/integration/{integration_id}/secrets", headers=auth_headers)
    assert listed.status_code == 200
    assert [secret["name"] for secret in listed.json()] == ["partner-api-key", "reporting-key"]

    # Pagination reaches the query: the sub-collection pages like every other list.
    paged = client.get(
        f"/api/v1/integration/{integration_id}/secrets?offset=1&limit=1", headers=auth_headers
    )
    assert paged.status_code == 200
    assert [secret["name"] for secret in paged.json()] == ["reporting-key"]
    assert (
        client.get(
            f"/api/v1/integration/{integration_id}/secrets?limit=0", headers=auth_headers
        ).status_code
        == 422
    )

    # Rotation answers 200 and still hides the value; an edit without one is legal,
    # because the value is write-only and a caller relabelling cannot resend it.
    rotated = client.put(
        f"/api/v1/integration/{integration_id}/secrets/reporting-key",
        json={"value": "rotated-key", "description": "rotated"},
        headers=auth_headers,
    )
    assert rotated.status_code == 200
    assert "value" not in rotated.json()
    assert rotated.json()["description"] == "rotated"

    relabelled = client.put(
        f"/api/v1/integration/{integration_id}/secrets/reporting-key",
        json={"description": "kept"},
        headers=auth_headers,
    )
    assert relabelled.status_code == 200
    assert relabelled.json()["description"] == "kept"

    # The unreferenced secret goes; the one a request field names is protected.
    removed = client.delete(
        f"/api/v1/integration/{integration_id}/secrets/reporting-key", headers=auth_headers
    )
    assert removed.status_code == 200
    referenced = client.delete(
        f"/api/v1/integration/{integration_id}/secrets/partner-api-key", headers=auth_headers
    )
    assert referenced.status_code == 409
    assert "still referenced" in referenced.json()["detail"]


def test_integration_secret_endpoints_reject_unknown_targets(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Every secret route answers 404 for an unknown parent or name.

    A sub-collection that ignored its parent id would let one provider's
    secrets be read through another's URL.
    """
    missing = "00000000-0000-0000-0000-000000000000"
    assert (
        client.post(
            f"/api/v1/integration/{missing}/secrets",
            json={"name": "k", "value": "v"},
            headers=auth_headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/integration/{missing}/secrets", headers=auth_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/integration/{missing}/secrets/whatever", headers=auth_headers
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/integration/{missing}/secrets/whatever",
            json={"value": "v"},
            headers=auth_headers,
        ).status_code
        == 404
    )

    created = client.post("/api/v1/integration/", json=integration_payload(), headers=auth_headers)
    integration_id = created.json()["id"]
    assert (
        client.delete(
            f"/api/v1/integration/{integration_id}/secrets/absent", headers=auth_headers
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/integration/{integration_id}/secrets/absent",
            json={"value": "v"},
            headers=auth_headers,
        ).status_code
        == 404
    )


def test_integration_update_replaces_operations(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Re-sending an operation replaces it instead of colliding with itself.

    Measured before the fix: the unit of work inserted the new rows before
    deleting the old ones, so a payload carrying an existing code violated
    uq_integration_operation_provider_code and surfaced as a 500 - which is
    every edit the UI makes, because the array is sent whole.
    """
    created = client.post(
        "/api/v1/integration/", json=integration_payload(), headers=auth_headers
    ).json()
    operations = created["operations"]
    assert len(operations) == 1
    kept_fields = len(operations[0]["fields"])
    assert kept_fields > 0

    same = _as_operation_request(operations[0])
    added = {**same, "code": "added-operation", "fields": []}
    provider_id = created["id"]
    response = client.patch(
        f"/api/v1/integration/{provider_id}",
        json={"operations": [same, added]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert {op["code"] for op in body["operations"]} == {same["code"], "added-operation"}
    replaced = next(op for op in body["operations"] if op["code"] == same["code"])
    assert len(replaced["fields"]) == kept_fields

    dropped = client.patch(
        f"/api/v1/integration/{provider_id}",
        json={"operations": [same]},
        headers=auth_headers,
    )
    assert dropped.status_code == 200
    assert [op["code"] for op in dropped.json()["operations"]] == [same["code"]]


def _as_operation_request(operation: dict[str, object]) -> dict[str, object]:
    """The read model minus the columns the server owns."""
    server_owned = {"id", "created_at", "updated_at", "created_by", "updated_by", "version"}
    request = {key: value for key, value in operation.items() if key not in server_owned}
    fields = request.get("fields")
    if isinstance(fields, list):
        request["fields"] = [
            {key: value for key, value in field.items() if key not in server_owned}
            for field in fields
        ]
    return request

def test_driver_constraint_violation_is_a_conflict(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A constraint the service did not pre-check answers 409, never a 500.

    Every constraint this app can violate is validated before the insert, so the
    driver only raises on a race - two requests creating the same code at once.
    That is why the mapping is asserted here instead of provoked: the caller must
    be able to tell a conflict from a broken server either way.
    """

    async def raise_integrity(*_args: object, **_kwargs: object) -> None:
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    monkeypatch.setattr(IntegrationProviderRepository, "create", raise_integrity)
    response = client.post(
        "/api/v1/integration/", json=integration_payload(), headers=auth_headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"
