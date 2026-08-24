"""Batch domain tests — CRUD through the HTTP API (standard pattern)."""

from fastapi.testclient import TestClient


class BatchCache:
    """A cache that records what it was asked to store and invalidate.

    Recording rather than mocking is what lets a test assert the key shape,
    which is where cross-user leaks would appear.
    """

    def __init__(self) -> None:
        """Start empty, with both call logs open for inspection."""
        self.values: dict[str, object] = {}
        self.invalidated_prefixes: list[str] = []
        self.set_keys: list[str] = []

    async def get_json(self, key: str) -> object | None:
        """Serve a stored value, or None on a miss."""
        return self.values.get(key)

    async def set_json(self, key: str, value: object, *, ttl_seconds: int) -> None:
        """Store the value and remember the key the router chose."""
        self.set_keys.append(key)
        self.values[key] = value

    async def invalidate(self, prefix: str) -> None:
        """Drop every key under the prefix and record that it happened."""
        self.invalidated_prefixes.append(prefix)
        self.values = {
            key: value for key, value in self.values.items() if not key.startswith(prefix)
        }


def test_create_batch(client: TestClient, auth_headers: dict[str, str]) -> None:
    """A 201 carries the id later calls address the row by."""
    response = client.post(
        "/api/v1/batch/", json={"name": "Batch 1", "description": "Batch job"}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Batch 1"
    assert body["description"] == "Batch job"
    assert "id" in body


def test_list_batches(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Two rows, so a query that returns only the first still fails."""
    client.post("/api/v1/batch/", json={"name": "Alpha"}, headers=auth_headers)
    client.post("/api/v1/batch/", json={"name": "Beta"}, headers=auth_headers)

    response = client.get("/api/v1/batch/", headers=auth_headers)
    assert response.status_code == 200
    names = [i["name"] for i in response.json()]
    assert "Alpha" in names
    assert "Beta" in names


def test_get_batch(client: TestClient, auth_headers: dict[str, str]) -> None:
    """The id from the create response resolves — the write really committed."""
    created = client.post("/api/v1/batch/", json={"name": "Glob"}, headers=auth_headers).json()
    batch_id = created["id"]

    response = client.get(f"/api/v1/batch/{batch_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Glob"


def test_get_batch_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """An unknown id answers 404, so the domain error reached the handler."""
    response = client.get(
        "/api/v1/batch/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404


def test_update_batch(client: TestClient, auth_headers: dict[str, str]) -> None:
    """A partial payload changes only the field it names."""
    created = client.post("/api/v1/batch/", json={"name": "Old"}, headers=auth_headers).json()
    batch_id = created["id"]

    response = client.put(f"/api/v1/batch/{batch_id}", json={"name": "New"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "New"


def test_update_batch_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Writing to a missing row is 404 rather than an implicit create."""
    response = client.put(
        "/api/v1/batch/00000000-0000-0000-0000-000000000000",
        json={"name": "New"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_delete_batch(client: TestClient, auth_headers: dict[str, str]) -> None:
    """The follow-up read proves the row is gone, not just that 200 was sent."""
    created = client.post("/api/v1/batch/", json={"name": "Temp"}, headers=auth_headers).json()
    batch_id = created["id"]

    response = client.delete(f"/api/v1/batch/{batch_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    response = client.get(f"/api/v1/batch/{batch_id}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_batch_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Deleting twice answers 404 — the second call is not a silent success."""
    response = client.delete(
        "/api/v1/batch/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404


def test_create_batch_missing_field_422(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Missing required field (name) → 422."""
    response = client.post("/api/v1/batch/", json={}, headers=auth_headers)
    assert response.status_code == 422


def test_batch_unauthorized_401(client: TestClient) -> None:
    """No token → 401 (all endpoints require auth)."""
    response = client.get("/api/v1/batch/")
    assert response.status_code == 401


def test_batch_reads_use_cache_and_writes_invalidate(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Cached reads are scoped per account, and every write drops the namespace.

    The asserted key shape carries the user id: without it one account would
    serve another account's rows from cache. The three invalidations cover
    create, update and delete, since a stale read after a write is the failure
    caching most easily introduces.
    """
    from app.main import app

    cache = BatchCache()
    app.state.redis_cache = cache

    created = client.post("/api/v1/batch/", json={"name": "Cached"}, headers=auth_headers).json()
    batch_id = created["id"]
    user_id = client.get("/api/v1/auth/me", headers=auth_headers).json()["id"]

    listed = client.get("/api/v1/batch/", headers=auth_headers).json()
    assert listed[0]["id"] == batch_id
    assert client.get("/api/v1/batch/", headers=auth_headers).json() == listed

    detail = client.get(f"/api/v1/batch/{batch_id}", headers=auth_headers).json()
    assert client.get(f"/api/v1/batch/{batch_id}", headers=auth_headers).json() == detail
    assert cache.set_keys == [
        f"batches:v1:{user_id}:list:0:50",
        f"batches:v1:{user_id}:detail:{batch_id}",
    ]

    assert (
        client.put(
            f"/api/v1/batch/{batch_id}", json={"name": "Updated"}, headers=auth_headers
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/batch/{batch_id}", headers=auth_headers).status_code == 200
    assert cache.invalidated_prefixes == ["batches", "batches", "batches"]
