# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Integer,
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
    __table_args__ = (
        UniqueConstraint("code", name="uq_integration_provider_code"),
        CheckConstraint(
            "transport IN ('HTTP_JSON', 'HTML_FORM')", name="ck_integration_provider_transport"
        ),
        # A bootstrap path is exactly the session-bearing transport: a screen GET
        # that mints the cookie belongs to no portal that answers without one.
        CheckConstraint(
            "transport = 'HTML_FORM' OR bootstrap_path IS NULL",
            name="ck_integration_provider_bootstrap",
        ),
        CheckConstraint("min_interval_ms >= 0", name="ck_integration_provider_min_interval"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(String(2048))
    # How the portal answers, which is the whole decoder choice. `HTTP_JSON` is an
    # API: a credential in the request, a JSON (or XML) body back. `HTML_FORM` is a
    # public screen with no API at all — measured 2026-09-13 on impfood.mfds.go.kr:
    # the list is `POST /CFCCC01F01/getList` as multipart with a session cookie and a
    # Referer, and the answer is the 658 KB screen, rows in `table.board_list`.
    transport: Mapped[str] = mapped_column(
        String(16), default="HTTP_JSON", server_default="HTTP_JSON"
    )
    # The screen that mints the session cookie, fetched once before the first call.
    # Without it that same POST answers a 5 KB `<title>Error</title>` page.
    bootstrap_path: Mapped[str | None] = mapped_column(String(512), default=None)
    # The floor on the gap between two calls to this host, in milliseconds. A
    # host's rate is the host's, not an operation's: measured 2026-09-13 on
    # impfood, 2 calls a second were answered and 3 were not - and the refusal
    # was a dropped connection on *every* path of the host, the nightly list
    # screen included, for about fifteen minutes. 0 is "as fast as the caller
    # asks", which is every API provider here.
    min_interval_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
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
