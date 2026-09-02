# ============================================================
# Imports
# ============================================================

from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.core.settings import settings
from app.dependencies.core import SessionDep
from app.models.user import User


# ============================================================
# Constants
# ============================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# The refresh token never reaches JavaScript: it travels in an httpOnly cookie,
# so a script that gets injected into the page can call /auth/refresh but cannot
# read the credential and keep it.
REFRESH_COOKIE_NAME = "refresh_token"

# Scoped to the auth routes: the browser then attaches the long-lived credential
# only to the two requests that spend it, instead of to every API call that has
# no use for it. The prefix is the one `main.py` mounts the versioned router at;
# a cookie written at another path is simply never sent back.
REFRESH_COOKIE_PATH = "/api/v1/auth"

# Lax, not None: the cookie is only ever spent by the app's own pages, and
# SameSite is what keeps another site from making the browser spend it.
REFRESH_COOKIE_SAMESITE = "lax"

SECONDS_PER_DAY = 86400

# OAuth2 password form — Annotated alias so routers never use inline Depends().
OAuth2FormDep = Annotated[OAuth2PasswordRequestForm, Depends()]


# ============================================================
# Functions
# ============================================================


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
) -> User:
    """Resolve the authenticated user from the Bearer token.

    Every failure is the same failure — the token does not identify a user — so
    it raises one core exception and the handler answers 401 with the
    WWW-Authenticate challenge (backend-exceptions.md).
    """
    subject = decode_access_token(token)
    if subject is None:
        raise AuthenticationError()
    try:
        user_id = UUID(subject)
    except ValueError:
        raise AuthenticationError() from None

    user = await session.get(User, user_id)
    if user is None:
        raise AuthenticationError()
    # Detach the user so the request handler can open its own transaction
    # via session.begin() — rollback would expire the attributes.
    session.expunge(user)
    await session.rollback()
    return user


def get_refresh_cookie(
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> str | None:
    """Read the refresh credential the browser attached, if it attached one.

    Optional rather than required: `/auth/logout` must answer the same way with
    or without a cookie, and `/auth/refresh` turns the absence into the same 401
    it gives an unknown token — a missing cookie and a rejected one are the same
    fact to a client, and telling them apart tells an attacker which is which.
    """
    return refresh_token


def get_response(response: Response) -> Response:
    """Hand the outgoing response to a handler that must set a cookie on it.

    A router may not declare `response: Response` directly — every parameter is
    a path, a body, a `*Dep` or a `*Query` (backend-router-params.md) — so the
    injection FastAPI already performs for dependencies is given a name here.
    """
    return response


def set_refresh_cookie(response: Response, token: str) -> None:
    """Write the session cookie the browser will present to `/auth/refresh`."""
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        token,
        max_age=settings.refresh_token_expire_days * SECONDS_PER_DAY,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=REFRESH_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Remove the session cookie on logout.

    The attributes must match the ones it was written with: a delete naming a
    different path leaves the original cookie in place, and the browser keeps
    presenting a token the server has already revoked.
    """
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=REFRESH_COOKIE_SAMESITE,
    )


# ============================================================
# Dependencies
# ============================================================

CurrentUserDep = Annotated[User, Depends(get_current_user)]
RefreshCookieDep = Annotated[str | None, Depends(get_refresh_cookie)]
ResponseDep = Annotated[Response, Depends(get_response)]
