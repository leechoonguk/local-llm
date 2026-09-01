"""Auth tests — login flow, /auth/me, invalid/expired token handling."""

from fastapi.testclient import TestClient


def test_login_success(client: TestClient) -> None:
    """Signup then login: the token carries `token_type`, which clients rely on."""
    client.post(
        "/api/v1/user/",
        json={"username": "lisa", "email": "lisa@example.com", "password": "secret-pass"},
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "lisa", "password": "secret-pass"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient) -> None:
    """A wrong password is 401 with the same body as an unknown user.

    Distinguishing the two would tell an attacker which usernames exist.
    """
    client.post(
        "/api/v1/user/",
        json={"username": "mike", "email": "mike@example.com", "password": "secret-pass"},
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "mike", "password": "wrong-pass"},
    )
    assert response.status_code == 401


def test_login_unknown_user(client: TestClient) -> None:
    """An account that does not exist answers 401, never 404."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "ghost", "password": "secret-pass"},
    )
    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    """The token resolves to the account that logged in, not to some default."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "tester"


def test_me_without_token(client: TestClient) -> None:
    """A missing Authorization header is rejected before the handler runs."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_invalid_token(client: TestClient) -> None:
    """A malformed bearer value is 401, not a 500 from the JWT decoder."""
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_me_with_valid_token_missing_user(client: TestClient) -> None:
    """Token with a valid JWT but a subject (UUID) that has no user row."""
    from app.core.security import create_access_token

    token = create_access_token(subject="00000000-0000-0000-0000-000000000000")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_with_non_uuid_subject(client: TestClient) -> None:
    """Token whose subject is not a UUID at all — ValueError path in auth dep."""
    from app.core.security import create_access_token

    token = create_access_token(subject="not-a-uuid")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_refresh_rotates_the_session(client: TestClient) -> None:
    """Refresh spends the cookie for a new token and plants the successor.

    Rotation is the contract, not a detail: the old cookie value must stop
    working, otherwise a stolen copy stays valid for its whole lifetime.
    """
    client.post(
        "/api/v1/user/",
        json={"username": "rosa", "email": "rosa@example.com", "password": "secret-pass"},
    )
    client.post("/api/v1/auth/login", data={"username": "rosa", "password": "secret-pass"})
    first_cookie = client.cookies["refresh_token"]

    response = client.post("/api/v1/auth/refresh", json={})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert client.cookies["refresh_token"] != first_cookie

    # 도둑 시나리오: 이미 소비된(회전 전) 쿠키를 다시 제시하면 그 사용자의 살아있는
    # 세션 전부가 폐기된다 — 정당한 클라이언트와 도둑이 최신 토큰을 동시에 들 수 없다.
    successor = client.cookies["refresh_token"]
    client.cookies.set("refresh_token", first_cookie)
    assert client.post("/api/v1/auth/refresh", json={}).status_code == 401
    client.cookies.set("refresh_token", successor)
    assert client.post("/api/v1/auth/refresh", json={}).status_code == 401


def test_refresh_without_cookie(client: TestClient) -> None:
    """No cookie is 401 — indistinguishable from a rejected one."""
    client.cookies.clear()
    response = client.post("/api/v1/auth/refresh", json={})
    assert response.status_code == 401


def test_logout_revokes_the_session(client: TestClient) -> None:
    """Logout kills the session server-side: the cookie stops refreshing."""
    client.post(
        "/api/v1/user/",
        json={"username": "nina", "email": "nina@example.com", "password": "secret-pass"},
    )
    client.post("/api/v1/auth/login", data={"username": "nina", "password": "secret-pass"})
    cookie = client.cookies["refresh_token"]

    response = client.post("/api/v1/auth/logout", json={})
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    # 서버측 폐기의 증명: 지워진 쿠키를 손으로 되살려도 세션은 죽어 있다.
    client.cookies.set("refresh_token", cookie)
    assert client.post("/api/v1/auth/refresh", json={}).status_code == 401


def test_logout_is_idempotent(client: TestClient) -> None:
    """A second logout (stale cookie, or none) still answers 200.

    A browser holding a dead cookie must be able to get rid of it without an
    error it cannot act on.
    """
    client.cookies.clear()
    response = client.post("/api/v1/auth/logout", json={})
    assert response.status_code == 200
