# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.integration.provider import PROVIDER_FK, Integration


if TYPE_CHECKING:
    from app.models.integration.field import IntegrationField


# ============================================================
# Constants
# ============================================================

#: A foreign-key target, not a credential — `S105` reads the *name*.
SECRET_FK = "integration_secret.id"  # noqa: S105


# ============================================================
# Classes
# ============================================================


class IntegrationSecret(Base, AuditMixin):
    """A named credential owned by one provider.

    Secrets live here rather than on the field rows that consume them: a key is
    rotated in one place, survives a full replacement of an operation's fields,
    and is stored once no matter how many operations send it.

    **A pool is a property of the secret, not of the field.** Secrets of one
    provider that share a `rotation_group` are interchangeable: a field bound to
    any of them may be sent with any other, and the client picks. The group
    lives here because the keys are the portal's and so is their quota - the
    six operations under `mfds-food-safety-korea` would otherwise each carry a
    list of the same three keys, and the list that missed the fourth key would
    be the one running that night.

    `exhausted_until` is the only runtime state on this table: the moment a
    key answered with the operation's quota code, plus the portal's window. A
    key past that moment is a candidate again. Written without the version
    bump (Core UPDATE): two processes marking the same key in the same second
    must both succeed, and no reader compares this column's revision.
    """

    __tablename__ = "integration_secret"
    __table_args__ = (
        UniqueConstraint("provider_id", "name", name="uq_integration_secret_provider_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(PROVIDER_FK, ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(String(512), default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rotation_group: Mapped[str | None] = mapped_column(String(64), default=None)
    exhausted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    provider: Mapped[Integration] = relationship(
        back_populates="secrets",
        lazy="raise_on_sql",
    )
    fields: Mapped[list[IntegrationField]] = relationship(
        back_populates="secret",
        lazy="raise_on_sql",
    )
