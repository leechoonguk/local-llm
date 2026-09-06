"""User domain tests — signup (public), CRUD, auth flow, conflict cases."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.schemas.user import UserReadResponse


def test_create_user_public(client: TestClient) -> None:
    """POST /user/ is public (no auth) — the signup endpoint."""
    response = client.post(
        "/api/v1/user/",
        json={"username": "alice", "email": "alice@example.com", "password": "secret-pass"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert "id" in body


def test_create_user_duplicate_username(client: TestClient) -> None:
    """A taken username answers 409, not 500 — the unique index is a contract.

    Without the service-level check the insert fails at the database and the
    caller sees an opaque error instead of a conflict.
    """
    client.post(
        "/api/v1/user/",
        json={"username": "dup", "email": "a@example.com", "password": "secret-pass"},
    )
    response = client.post(
        "/api/v1/user/",
        json={"username": "dup", "email": "b@example.com", "password": "secret-pass"},
    )
    assert response.status_code == 409


def test_create_user_duplicate_email(client: TestClient) -> None:
    """Email is unique independently of username — both indexes must be honoured."""
    client.post(
        "/api/v1/user/",
        json={"username": "one", "email": "same@example.com", "password": "secret-pass"},
    )
    response = client.post(
        "/api/v1/user/",
        json={"username": "two", "email": "same@example.com", "password": "secret-pass"},
    )
    assert response.status_code == 409


def test_list_users(client: TestClient, auth_headers: dict[str, str]) -> None:
    """The collection read requires a token and shows rows other calls created."""
    response = client.get("/api/v1/user/", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    usernames = [u["username"] for u in body["items"]]
    assert "tester" in usernames  # created by the auth_headers fixture
    # The total is the collection's size, not the page's: a client that shows
    # "1-10 of N" reads it on page one, before it has seen the last row.
    assert body["total"] == len(body["items"])


def test_list_users_field_filters(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Each field is its own query parameter, and an empty value is refused.

    The empty string is a 422 rather than "no filter": two spellings of the same
    request is how a client ends up sending `username=` forever and believing
    the filter is off.
    """
    client.post(
        "/api/v1/user/",
        json={
            "username": "filterable",
            "email": "filterable@example.com",
            "password": "secret-pass",
        },
    )

    by_name = client.get("/api/v1/user/", params={"username": "FILTER"}, headers=auth_headers)
    assert by_name.status_code == 200
    assert [user["username"] for user in by_name.json()["items"]] == ["filterable"]
    assert by_name.json()["total"] == 1

    by_email = client.get(
        "/api/v1/user/", params={"email": "filterable@example.com"}, headers=auth_headers
    )
    assert [user["username"] for user in by_email.json()["items"]] == ["filterable"]

    # The two filters narrow together: this username never had that email.
    both = client.get(
        "/api/v1/user/",
        params={"username": "filterable", "email": "tester@example.com"},
        headers=auth_headers,
    )
    assert both.json() == {"items": [], "total": 0}

    empty = client.get("/api/v1/user/", params={"username": ""}, headers=auth_headers)
    assert empty.status_code == 422


def test_get_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    """A row created through the API is addressable by the id the API returned.

    Chaining the id here is what proves the create response is usable, not just
    well-shaped.
    """
    created = client.post(
        "/api/v1/user/",
        json={"username": "bob", "email": "bob@example.com", "password": "secret-pass"},
    ).json()
    user_id = created["id"]

    response = client.get(f"/api/v1/user/{user_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "bob"


def test_get_user_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """An unknown id answers 404 — the domain exception reaches the handler."""
    response = client.get("/api/v1/user/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert response.status_code == 404


def test_update_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    """A partial payload changes only the field it names.

    `exclude_unset` is what keeps the untouched columns alive; without it the
    other fields would be overwritten with defaults.
    """
    created = client.post(
        "/api/v1/user/",
        json={"username": "carol", "email": "carol@example.com", "password": "secret-pass"},
    ).json()
    user_id = created["id"]

    response = client.patch(
        f"/api/v1/user/{user_id}", json={"email": "new@example.com"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"


def test_update_user_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Writing to a missing row answers 404 instead of creating it."""
    response = client.patch(
        "/api/v1/user/00000000-0000-0000-0000-000000000000",
        json={"email": "x@example.com"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_delete_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    """The row is gone afterwards, which the follow-up read proves.

    Asserting only the 200 would pass for a delete that never committed.
    """
    created = client.post(
        "/api/v1/user/",
        json={"username": "dave", "email": "dave@example.com", "password": "secret-pass"},
    ).json()
    user_id = created["id"]

    response = client.delete(f"/api/v1/user/{user_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    response = client.get(f"/api/v1/user/{user_id}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_user_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Deleting twice is a 404, not a silent success — the caller can tell."""
    response = client.delete(
        "/api/v1/user/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404


def test_create_user_missing_field_422(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Missing required field (name) → 422."""
    response = client.post("/api/v1/user/", json={}, headers=auth_headers)
    assert response.status_code == 422


def test_create_user_rejects_values_only_the_form_used_to_refuse(client: TestClient) -> None:
    """The API refuses what the browser form refuses.

    Measured before this was enforced: `curl` created a user with the email
    `not-an-email` and a one-character password, and the API answered 201. A
    rule that lives only in the dialog is a rule any other client ignores.
    """
    weak = client.post(
        "/api/v1/user/",
        json={"username": "weak", "email": "weak@example.com", "password": "x"},
    )
    assert weak.status_code == 422

    malformed = client.post(
        "/api/v1/user/",
        json={"username": "bad-email", "email": "not-an-email", "password": "secret-pass"},
    )
    assert malformed.status_code == 422

    too_long = client.post(
        "/api/v1/user/",
        json={"username": "a" * 51, "email": "long@example.com", "password": "secret-pass"},
    )
    assert too_long.status_code == 422

    accepted = client.post(
        "/api/v1/user/",
        json={"username": "fine", "email": "fine@example.com", "password": "secret-pass"},
    )
    assert accepted.status_code == 201


def test_list_users_reads_a_row_the_write_rules_would_now_reject(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A stored value the request rules forbid is still readable.

    Measured: when the email pattern lived on `UserBase`, `UserReadResponse`
    inherited it and one row written before the rule existed made `GET /user/`
    answer 500 for every caller - the whole list, not that row. Input rules
    belong on input models, and this test is what says so.
    """
    stored = UserReadResponse(
        id=uuid4(),
        username="legacy",
        email="not-an-email",
        created_by="system",
        updated_by=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        version=1,
    )
    assert stored.email == "not-an-email"

    response = client.get("/api/v1/user/", headers=auth_headers)
    assert response.status_code == 200


def test_user_unauthorized_401(client: TestClient) -> None:
    """No token → 401 (all endpoints require auth)."""
    response = client.get("/api/v1/user/")
    assert response.status_code == 401
