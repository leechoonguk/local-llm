# ============================================================
# Imports
# ============================================================

import uuid
from uuid import uuid4

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Classes
# ============================================================

class Notice(Base, AuditMixin):
    __tablename__ = "notice"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(default=False)
    published_at: Mapped[str | None] = mapped_column(default=None)
