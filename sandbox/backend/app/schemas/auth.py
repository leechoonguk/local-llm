# ============================================================
# Imports
# ============================================================

from pydantic import BaseModel, ConfigDict


# ============================================================
# Classes
# ============================================================

class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
