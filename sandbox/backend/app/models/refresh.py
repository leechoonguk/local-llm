# ============================================================
# Imports
# ============================================================

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Classes
# ============================================================


class Refresh(Base, AuditMixin):
    """One issued refresh token, stored as a digest.

    The row is the server-side half of a session: it is what makes a refresh
    token revocable at all. Only the SHA-256 digest is kept — a database dump
    then carries nothing an attacker can present, and the lookup stays a single
    indexed equality (the token is 256 bits of `secrets` output, so a password
    KDF would only add ~25 ms per rotation against an unguessable value).

    `revoked_at` is set instead of deleting the row: rotation must be able to
    tell "this token was already used" from "this token never existed", and only
    the first case means the token leaked.
    """

    __tablename__ = "refresh"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
