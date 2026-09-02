# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
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

SECRET_FK = "integration_secret.id"


# ============================================================
# Classes
# ============================================================


class IntegrationSecret(Base, AuditMixin):
    """A named credential owned by one provider.

    Secrets live here rather than on the field rows that consume them: a key is
    rotated in one place, survives a full replacement of an operation's fields,
    and is stored once no matter how many operations send it.
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
    provider: Mapped[Integration] = relationship(
        back_populates="secrets",
        lazy="raise_on_sql",
    )
    fields: Mapped[list[IntegrationField]] = relationship(
        back_populates="secret",
        lazy="raise_on_sql",
    )
