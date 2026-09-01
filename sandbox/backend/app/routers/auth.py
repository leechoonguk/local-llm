# ============================================================
# Imports
# ============================================================

from fastapi import APIRouter

from app.core.security import create_access_token
from app.dependencies.auth import (
    CurrentUserDep,
    OAuth2FormDep,
    RefreshCookieDep,
    ResponseDep,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from app.dependencies.services import RefreshServiceDep, UserServiceDep
from app.schemas.auth import LogoutResponse, SessionRequest, TokenResponse
from app.schemas.refresh import RefreshCreateRequest
from app.schemas.user import UserReadResponse, to_read


# ============================================================
# Router
# ============================================================

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    form_data: OAuth2FormDep,
    response: ResponseDep,
    user_service: UserServiceDep,
    refresh_service: RefreshServiceDep,
) -> TokenResponse:
    """Authenticate a user, return a short-lived access token, set the session cookie.

    Only the access token is in the body. The refresh token goes out as an
    httpOnly cookie and is never handed to JavaScript, so the long-lived half of
    the session cannot be read out of the page.
    """
    user = await user_service.authenticate(form_data.username, form_data.password)
    token = await refresh_service.create_refresh(
        RefreshCreateRequest(user_id=user.id), created_by=user.username
    )
    set_refresh_cookie(response, token)
    return TokenResponse(access_token=create_access_token(subject=str(user.id)))


@router.post("/refresh")
async def refresh(
    data: SessionRequest,
    refresh_token: RefreshCookieDep,
    response: ResponseDep,
    refresh_service: RefreshServiceDep,
    user_service: UserServiceDep,
) -> TokenResponse:
    """Spend the session cookie for a new access token and a new cookie.

    Public by necessity: it is the request a client makes precisely because its
    access token is gone or expired, so requiring one would make refreshing
    possible only while it is unnecessary. The cookie is the credential, and
    rotation makes a stolen copy usable at most once.
    """
    user_id, successor = await refresh_service.create_rotated_refresh(
        refresh_token, created_by="refresh"
    )
    user = await user_service.get_user(user_id)
    set_refresh_cookie(response, successor)
    return TokenResponse(access_token=create_access_token(subject=str(user.id)))


@router.post("/logout")
async def logout(
    data: SessionRequest,
    refresh_token: RefreshCookieDep,
    response: ResponseDep,
    refresh_service: RefreshServiceDep,
) -> LogoutResponse:
    """Revoke the session cookie's token and clear the cookie.

    Public and idempotent on purpose: a client whose access token has already
    expired must still be able to end its session server-side, and a browser
    holding a stale cookie must be able to get rid of it.
    """
    await refresh_service.delete_session(refresh_token, revoked_by="logout")
    clear_refresh_cookie(response)
    return LogoutResponse()


@router.get("/me")
async def read_me(current_user: CurrentUserDep) -> UserReadResponse:
    """Return the currently authenticated user."""
    return to_read(current_user)
