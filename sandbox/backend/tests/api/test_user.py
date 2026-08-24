"""User domain tests — signup (public), CRUD, auth flow, conflict cases."""

from fastapi.testclient import TestClient


def test_create_user_public(client: TestClient) -> None:
    """POST /user/ is public (no auth) — the signup endpoint."""
    response = client.post(
        "/api/v1/user/",
        json={"username": "alice", "email": "alice@example.com", "password": "secret"},
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
        "/api/v1/user/", json={"username": "dup", "email": "a@example.com", "password": "secret"}
    )
    response = client.post(
        "/api/v1/user/", json={"username": "dup", "email": "b@example.com", "password": "secret"}
    )
    assert response.status_code == 409


def test_create_user_duplicate_email(client: TestClient) -> None:
    """Email is unique independently of username — both indexes must be honoured."""
    client.post(
        "/api/v1/user/", json={"username": "one", "email": "same@example.com", "password": "secret"}
    )
    response = client.post(
        "/api/v1/user/", json={"username": "two", "email": "same@example.com", "password": "secret"}
    )
    assert response.status_code == 409


def test_list_users(client: TestClient, auth_headers: dict[str, str]) -> None:
    """The collection read requires a token and shows rows other calls created."""
    response = client.get("/api/v1/user/", headers=auth_headers)
    assert response.status_code == 200
    usernames = [u["username"] for u in response.json()]
    assert "tester" in usernames  # created by the auth_headers fixture


def test_get_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    """A row created through the API is addressable by the id the API returned.

    Chaining the id here is what proves the create response is usable, not just
    well-shaped.
    """
    created = client.post(
        "/api/v1/user/", json={"username": "bob", "email": "bob@example.com", "password": "secret"}
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
        json={"username": "carol", "email": "carol@example.com", "password": "secret"},
    ).json()
    user_id = created["id"]

    response = client.put(
        f"/api/v1/user/{user_id}", json={"email": "new@example.com"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"


def test_update_user_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Writing to a missing row answers 404 instead of creating it."""
    response = client.put(
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
        json={"username": "dave", "email": "dave@example.com", "password": "secret"},
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


def test_user_unauthorized_401(client: TestClient) -> None:
    """No token → 401 (all endpoints require auth)."""
    response = client.get("/api/v1/user/")
    assert response.status_code == 401
