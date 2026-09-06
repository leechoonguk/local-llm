"""Batch domain tests — CRUD through the HTTP API (standard pattern)."""

from typing import Any, cast
from uuid import UUID

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
    body = response.json()
    names = [i["name"] for i in body["items"]]
    assert "Alpha" in names
    assert "Beta" in names
    assert body["total"] == 2


def test_list_batches_name_filter(client: TestClient, auth_headers: dict[str, str]) -> None:
    """`?name=` narrows the page and the total together, and rejects an empty value.

    The filter is part of the cache key, so the assertion runs a filtered read
    after an unfiltered one: a key that ignored it would serve these two rows as
    the whole collection to the next caller.
    """
    for name in ("Nightly sync", "Weekly report"):
        client.post(
            "/api/v1/batch/",
            json={"code": JOB_CODE, "name": name, "cron": CRON},
            headers=auth_headers,
        )
    client.get("/api/v1/batch/", headers=auth_headers)

    response = client.get("/api/v1/batch/", params={"name": "NIGHTLY"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert [item["name"] for item in body["items"]] == ["Nightly sync"]
    assert body["total"] == 1

    unmatched = client.get("/api/v1/batch/", params={"name": "nothing"}, headers=auth_headers)
    assert unmatched.json() == {"items": [], "total": 0}

    empty = client.get("/api/v1/batch/", params={"name": ""}, headers=auth_headers)
    assert empty.status_code == 422


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
    assert listed["items"][0]["id"] == batch_id
    assert client.get("/api/v1/batch/", headers=auth_headers).json() == listed

    detail = client.get(f"/api/v1/batch/{batch_id}", headers=auth_headers).json()
    assert client.get(f"/api/v1/batch/{batch_id}", headers=auth_headers).json() == detail
    assert cache.set_keys == [
        # The trailing segment is the name filter, empty on an unfiltered read:
        # a filtered page and the whole collection must not share a key.
        f"batches:v1:{user_id}:list:0:50:",
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


def test_list_reports_the_live_run_state(client: TestClient, auth_headers: dict[str, str]) -> None:
    """`running` is the scheduler's answer at read time, never the cached row's.

    The list is cached for a minute and a run lasts seconds, so the flag is
    stamped after the cache is read: the assertion reads the collection once to
    fill the cache, marks the schedule as in flight, and reads again. A `running`
    that travelled with the cached body would still say false here — and the stop
    button beside it would cancel nothing.
    """
    from app.main import app

    scheduler = BatchScheduler()
    app.state.scheduler = scheduler

    created = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "Watched", "cron": CRON},
        headers=auth_headers,
    ).json()
    batch_id = created["id"]
    assert created["running"] is False

    first = client.get("/api/v1/batch/", headers=auth_headers).json()
    assert [row["running"] for row in first["items"] if row["id"] == batch_id] == [False]

    # What `run_now` produces: the task map the scheduler cancels from.
    scheduler._running[UUID(batch_id)] = cast(Any, object())
    cached = client.get("/api/v1/batch/", headers=auth_headers).json()
    assert [row["running"] for row in cached["items"] if row["id"] == batch_id] == [True]
    assert client.get(f"/api/v1/batch/{batch_id}", headers=auth_headers).json()["running"] is True

    scheduler._running.clear()
    assert client.get(f"/api/v1/batch/{batch_id}", headers=auth_headers).json()["running"] is False

    client.delete(f"/api/v1/batch/{batch_id}", headers=auth_headers)
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


def test_list_batch_runs_answers_history_and_404(client, auth_headers) -> None:
    """The run log is reachable per schedule, and an unknown schedule is a 404.

    An empty history must come from a schedule that exists — an unknown id
    answering `[]` would read as "never ran" for a typo'd UUID.
    """
    created = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "history", "cron": CRON},
        headers=auth_headers,
    )
    batch_id = created.json()["id"]

    listed = client.get(f"/api/v1/batch/{batch_id}/runs", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json() == {"items": [], "total": 0}

    missing = client.get(
        "/api/v1/batch/00000000-0000-0000-0000-000000000000/runs", headers=auth_headers
    )
    assert missing.status_code == 404

    client.delete(f"/api/v1/batch/{batch_id}", headers=auth_headers)


def test_list_batch_run_steps_reads_one_run_and_guards_its_parentage(client, auth_headers) -> None:
    """Steps hang off a run, and the path's claimed parent must be the real one.

    Rows are seeded through the client's own portal — the scheduler that would
    normally write them is disabled under `settings.env == "test"`. A run
    reached through a schedule that is not its parent answers 404: anything
    else leaks another schedule's history to whoever guesses a UUID.
    """
    from uuid import UUID

    from app.dependencies import core as deps_core
    from app.services.batch.run import BatchRunService
    from app.services.batch.step import BatchStepService

    created = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "steps", "cron": CRON},
        headers=auth_headers,
    )
    batch_id = created.json()["id"]
    other = client.post(
        "/api/v1/batch/",
        json={"code": JOB_CODE, "name": "other", "cron": CRON},
        headers=auth_headers,
    )
    other_id = other.json()["id"]

    async def _seed() -> str:
        async with deps_core.async_session_factory() as session:
            run = await BatchRunService(session).create_started_run(
                UUID(batch_id), JOB_CODE, "MANUAL", "tester"
            )
        async with deps_core.async_session_factory() as session:
            await BatchStepService(session).create_finished_step(
                run.id, 1, 5, "tester", range_start=1, range_end=1000, received=1000, written=964
            )
        return str(run.id)

    run_id = client.portal.call(_seed)

    listed = client.get(f"/api/v1/batch/{batch_id}/runs/{run_id}/steps", headers=auth_headers)
    assert listed.status_code == 200
    steps = listed.json()
    assert [(s["sequence"], s["written"]) for s in steps["items"]] == [(1, 964)]
    assert steps["total"] == 1

    runs = client.get(f"/api/v1/batch/{batch_id}/runs", headers=auth_headers)
    assert [r["id"] for r in runs.json()["items"]] == [run_id]

    foreign = client.get(f"/api/v1/batch/{other_id}/runs/{run_id}/steps", headers=auth_headers)
    assert foreign.status_code == 404

    missing = client.get(
        f"/api/v1/batch/{batch_id}/runs/00000000-0000-0000-0000-000000000000/steps",
        headers=auth_headers,
    )
    assert missing.status_code == 404

    client.delete(f"/api/v1/batch/{batch_id}", headers=auth_headers)
    client.delete(f"/api/v1/batch/{other_id}", headers=auth_headers)
