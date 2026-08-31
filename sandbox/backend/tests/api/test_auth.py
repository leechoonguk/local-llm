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
