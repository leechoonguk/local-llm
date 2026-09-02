# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import CHILD_CASCADE, AuditMixin, Base


if TYPE_CHECKING:
    from app.models.integration.operation import IntegrationOperation
    from app.models.integration.secret import IntegrationSecret


# ============================================================
# Constants
# ============================================================

PROVIDER_FK = "integration_provider.id"


# ============================================================
# Classes
# ============================================================


class Integration(Base, AuditMixin):
    __tablename__ = "integration_provider"
    __table_args__ = (UniqueConstraint("code", name="uq_integration_provider_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(String(2048))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    operations: Mapped[list[IntegrationOperation]] = relationship(
        back_populates="provider",
        cascade=CHILD_CASCADE,
        passive_deletes=True,
        lazy="raise_on_sql",
    )
    secrets: Mapped[list[IntegrationSecret]] = relationship(
        back_populates="provider",
        cascade=CHILD_CASCADE,
        passive_deletes=True,
        lazy="raise_on_sql",
    )
