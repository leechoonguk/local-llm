# ============================================================
# Imports
# ============================================================

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.settings import settings


# ============================================================
# Constants
# ============================================================

password_hash = PasswordHash.recommended()

# 32 bytes = 256 bits of entropy from the OS CSPRNG. The refresh token is a
# bearer credential with no structure to verify, so its only defence is being
# unguessable; at this width a digest lookup needs no password KDF.
REFRESH_TOKEN_BYTES = 32


# ============================================================
# Functions
# ============================================================


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token with the given subject (user id)."""
    minutes = settings.access_token_expire_minutes
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=minutes))
    # `iat` dates the token: without it a leaked token cannot be told apart from
    # a fresh one, and a future revocation window has nothing to compare against.
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(UTC)}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    """Decode a JWT and return the subject (user id), or None when invalid."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            # A token without `exp` never expires and a token without `sub`
            # authenticates nobody — both are rejected here, not downstream.
            options={"require": ["exp", "sub"]},
        )
    except InvalidTokenError:
        return None
    return payload.get("sub")


def create_refresh_token() -> str:
    """Mint an opaque refresh token.

    Deliberately not a JWT: a signed refresh token is valid until it expires,
    whatever the server decides afterwards. An opaque secret carries no claims,
    so the only thing that can answer "is this session still alive" is the
    `refresh` row — which is what makes logout and reuse detection real.
    """
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """Digest a refresh token for storage and lookup.

    SHA-256, not argon2: the input is 256 bits of CSPRNG output, so there is no
    dictionary to slow down, and a refresh runs on the request path where a
    ~25 ms KDF would be paid by every rotation.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def refresh_token_expires_at() -> datetime:
    """The deadline every newly issued refresh token carries.

    One expression for login and for every rotation. A successor that inherited
    its predecessor's deadline would end the session mid-work; a deadline reset
    without a ceiling would make it immortal. Both come from spelling this in
    two places.
    """
    return datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
