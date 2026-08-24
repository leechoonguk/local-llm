# ============================================================
# Imports
# ============================================================

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.dependencies.core import SessionDep
from app.models.user import User


# ============================================================
# Constants
# ============================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

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


# ============================================================
# Dependencies
# ============================================================

CurrentUserDep = Annotated[User, Depends(get_current_user)]
