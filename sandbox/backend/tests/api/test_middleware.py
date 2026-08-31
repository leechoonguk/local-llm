"""Middleware behavior tests for browser-origin CSRF protection."""

from fastapi.testclient import TestClient


SIGNUP_PAYLOAD = {
    "username": "csrf-user",
    "email": "csrf-user@example.com",
    "password": "secret-pass",
}


def test_trusted_host_rejects_an_unknown_host_header(client: TestClient) -> None:
    """A request for a host we do not serve is refused before anything else runs.

    Host header poisoning is how a generated password-reset URL ends up pointing
    at an attacker's domain; the allowlist is the only thing that stops it.
    """
    response = client.get("/api/v1/auth/me", headers={"Host": "attacker.example"})

    assert response.status_code == 400


def test_trusted_host_allows_a_configured_host(client: TestClient) -> None:
    """A configured host reaches the app — the 401 comes from auth, not the guard.

    Without this half, an allowlist that refuses everything would look correct.
    """
    assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_rejects_unsafe_request_from_untrusted_origin(client: TestClient) -> None:
    """A browser POST from another site is refused with the Vary header set.

    `Vary` matters as much as the 403: without it a cache could serve the
    allowed response to a request from a different origin.
    """
    response = client.post(
        "/api/v1/user/",
        json=SIGNUP_PAYLOAD,
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF validation failed"}
    assert response.headers["Vary"] == "Origin, Sec-Fetch-Site"


def test_csrf_rejects_cross_site_fetch_metadata(client: TestClient) -> None:
    """Fetch Metadata alone is enough to refuse — no Origin header required."""
    response = client.post(
        "/api/v1/user/",
        json=SIGNUP_PAYLOAD,
        headers={"Sec-Fetch-Site": "cross-site"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF validation failed"}


def test_csrf_allows_unsafe_request_from_trusted_origin(client: TestClient) -> None:
    """The configured dev origin still works — the guard must not break the app."""
    response = client.post(
        "/api/v1/user/",
        json=SIGNUP_PAYLOAD,
        headers={
            "Origin": "http://localhost:25173",
            "Sec-Fetch-Site": "same-site",
        },
    )

    assert response.status_code == 201
    assert set(response.headers["Vary"].replace(" ", "").split(",")) == {
        "Origin",
        "Sec-Fetch-Site",
    }


def test_csrf_does_not_block_safe_cross_site_request(client: TestClient) -> None:
    """A GET is never refused by CSRF: 401 here comes from auth, not the guard."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Sec-Fetch-Site": "cross-site"},
    )

    assert response.status_code == 401
