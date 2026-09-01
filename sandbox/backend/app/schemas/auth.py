# ============================================================
# Imports
# ============================================================

from pydantic import BaseModel, ConfigDict


# ============================================================
# Classes
# ============================================================

class SessionRequest(BaseModel):
    """The body of `/auth/refresh` and `/auth/logout`: deliberately empty.

    Both endpoints are authenticated by the refresh cookie, never by anything
    the caller writes, so there is no field to accept — and `extra="forbid"`
    means a client that tries to send a token in the body is rejected instead of
    being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"


class LogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
