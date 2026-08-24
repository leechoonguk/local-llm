"""Core security tests — password hashing + JWT encode/decode."""

from datetime import UTC, datetime, timedelta

import jwt

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    """The stored value is not the password, and only the password verifies.

    Both halves matter: a hash that verifies everything is as broken as one
    that stores plaintext.
    """
    hashed = hash_password("secret")
    assert hashed != "secret"
    assert verify_password("secret", hashed)
    assert not verify_password("wrong", hashed)


def test_password_hash_is_salted() -> None:
    """Equal passwords hash differently, so a leak cannot be attacked in bulk."""
    assert hash_password("secret") != hash_password("secret")


def test_create_and_decode_access_token() -> None:
    """The subject survives the round trip — that identity is what auth reads."""
    token = create_access_token(subject="user-123")
    assert decode_access_token(token) == "user-123"


def test_token_expiry() -> None:
    """An elapsed lifetime yields no subject rather than an exception.

    The decoder returning None is what lets the auth dependency answer 401.
    """
    token = create_access_token(subject="u", expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


def test_decode_invalid_token() -> None:
    """Garbage in the header is rejected without reaching the handler."""
    assert decode_access_token("not-a-jwt") is None


def test_decode_tampered_token() -> None:
    """A flipped signature byte invalidates the whole token.

    This is the property that makes the signature worth computing.
    """
    token = create_access_token(subject="u")
    tampered = token[:-2] + ("ab" if token[-2:] != "ab" else "cd")
    assert decode_access_token(tampered) is None


def test_decode_token_wrong_algorithm(monkeypatch) -> None:
    """A token signed with a different algorithm is rejected."""
    from app.core.settings import settings

    monkeypatch.setattr(settings, "secret_key", "t" * 64)
    token = jwt.encode(
        {"sub": "u", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.secret_key,
        algorithm="HS512",
    )
    assert decode_access_token(token) is None
