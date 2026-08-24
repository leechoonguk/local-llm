# ============================================================
# Imports
# ============================================================

from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.settings import settings


# ============================================================
# Constants
# ============================================================

password_hash = PasswordHash.recommended()


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
