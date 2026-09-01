"""Batch domain tests — CRUD through the HTTP API (standard pattern)."""

from fastapi.testclient import TestClient

from app.core.scheduler import BatchScheduler


CRON = "0 3 * * *"

JOB_CODE = "purge_expired_refreshes"


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
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Batch 1", "description": "Batch job", "cron": CRON},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Batch 1"
    assert body["description"] == "Batch job"
    assert "id" in body


def test_list_batches(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Two rows, so a query that returns only the first still fails."""
    client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Alpha", "cron": CRON},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Beta", "cron": CRON},
        headers=auth_headers,
    )

    response = client.get("/api/v1/batch/", headers=auth_headers)
    assert response.status_code == 200
    names = [i["name"] for i in response.json()]
    assert "Alpha" in names
    assert "Beta" in names


def test_get_batch(client: TestClient, auth_headers: dict[str, str]) -> None:
    """The id from the create response resolves — the write really committed."""
    created = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Glob", "cron": CRON},
        headers=auth_headers,
    ).json()
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
    created = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Old", "cron": CRON},
        headers=auth_headers,
    ).json()
    batch_id = created["id"]

    response = client.patch(f"/api/v1/batch/{batch_id}", json={"name": "New"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "New"


def test_update_batch_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Writing to a missing row is 404 rather than an implicit create."""
    response = client.patch(
        "/api/v1/batch/00000000-0000-0000-0000-000000000000",
        json={"name": "New"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_delete_batch(client: TestClient, auth_headers: dict[str, str]) -> None:
    """The follow-up read proves the row is gone, not just that 200 was sent."""
    created = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Temp", "cron": CRON},
        headers=auth_headers,
    ).json()
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

    created = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Cached", "cron": CRON},
        headers=auth_headers,
    ).json()
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
        client.patch(
            f"/api/v1/batch/{batch_id}", json={"name": "Updated"}, headers=auth_headers
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/batch/{batch_id}", headers=auth_headers).status_code == 200
    assert cache.invalidated_prefixes == ["batches", "batches", "batches"]


def test_create_batch_unknown_code_422(client: TestClient, auth_headers: dict[str, str]) -> None:
    """A code no build can run is refused at the boundary, not discovered at 03:00."""
    response = client.post(
        "/api/v1/batch/",
        json={"code": "job_from_the_future", "name": "Ghost", "cron": CRON},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_batch_broken_cron_422(client: TestClient, auth_headers: dict[str, str]) -> None:
    """An unparseable cron is a job that never fires — the write is the last check."""
    response = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Ghost", "cron": "every tuesday"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_batch_writes_drive_the_running_scheduler(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The row is the schedule, so every write has to reach the live scheduler.

    Create schedules it, `enabled=false` stops it, and the delete removes it —
    a row that changed without the scheduler changing is the failure this
    endpoint exists to prevent.
    """
    from app.main import app

    scheduler = BatchScheduler()
    app.state.scheduler = scheduler

    created = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Scheduled", "cron": CRON},
        headers=auth_headers,
    ).json()
    batch_id = created["id"]
    assert [job.id for job in scheduler._scheduler.get_jobs()] == [batch_id]

    client.patch(f"/api/v1/batch/{batch_id}", json={"cron": "30 4 * * *"}, headers=auth_headers)
    assert "hour='4'" in str(scheduler._scheduler.get_jobs()[0].trigger)

    client.patch(f"/api/v1/batch/{batch_id}", json={"enabled": False}, headers=auth_headers)
    assert scheduler._scheduler.get_jobs() == []

    client.patch(f"/api/v1/batch/{batch_id}", json={"enabled": True}, headers=auth_headers)
    assert [job.id for job in scheduler._scheduler.get_jobs()] == [batch_id]

    client.delete(f"/api/v1/batch/{batch_id}", headers=auth_headers)
    assert scheduler._scheduler.get_jobs() == []

    app.state.scheduler = None


def test_run_and_stop_a_batch_job(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Running by hand and stopping the run are one endpoint over the wanted state.

    Neither touches the schedule: the row keeps its cron and its `enabled` flag,
    which is what separates "run it now" from "activate it".
    """
    from app.main import app

    scheduler = BatchScheduler()
    app.state.scheduler = scheduler

    created = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Runnable", "cron": CRON, "enabled": False},
        headers=auth_headers,
    ).json()
    batch_id = created["id"]

    started = client.post(
        f"/api/v1/batch/{batch_id}/run", json={"running": True}, headers=auth_headers
    )
    assert started.status_code == 200
    assert started.json() == {"id": batch_id, "code": JOB_CODE, "running": True}

    stopped = client.post(
        f"/api/v1/batch/{batch_id}/run", json={"running": False}, headers=auth_headers
    )
    assert stopped.status_code == 200
    assert stopped.json()["running"] is False

    assert client.get(f"/api/v1/batch/{batch_id}", headers=auth_headers).json()["enabled"] is False
    client.delete(f"/api/v1/batch/{batch_id}", headers=auth_headers)
    app.state.scheduler = None


def test_run_batch_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """An unknown id is 404 before the scheduler is consulted."""
    response = client.post(
        "/api/v1/batch/00000000-0000-0000-0000-000000000000/run",
        json={"running": True},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_run_batch_without_a_scheduler_409(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A process that runs no jobs says so, instead of accepting a run nobody executes."""
    created = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Unscheduled", "cron": CRON},
        headers=auth_headers,
    ).json()

    response = client.post(
        f"/api/v1/batch/{created['id']}/run", json={"running": True}, headers=auth_headers
    )

    assert response.status_code == 409
    client.delete(f"/api/v1/batch/{created['id']}", headers=auth_headers)
