# ============================================================
# Imports
# ============================================================

from fastapi import APIRouter

from app.core.security import create_access_token
from app.dependencies.auth import CurrentUserDep, OAuth2FormDep
from app.dependencies.services import UserServiceDep
from app.schemas.auth import TokenResponse
from app.schemas.user import UserReadResponse, to_read


# ============================================================
# Router
# ============================================================

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    form_data: OAuth2FormDep,
    user_service: UserServiceDep,
) -> TokenResponse:
    """Authenticate a user by username + password, return a JWT access token."""
    user = await user_service.authenticate(form_data.username, form_data.password)
    return TokenResponse(access_token=create_access_token(subject=str(user.id)))


@router.get("/me")
async def read_me(current_user: CurrentUserDep) -> UserReadResponse:
    """Return the currently authenticated user."""
    return to_read(current_user)
