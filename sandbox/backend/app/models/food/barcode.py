# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Classes
# ============================================================


class FoodBarcode(Base, AuditMixin):
    """식품 바코드 품목정보 원장 — our own copy of the I2570 records, one row per item.

    The name carries the portal, not just the record: four sibling ledgers are
    coming from the same 식품안전나라 services (`food_report`,
    `food_classification`, `food_material`, `food_test_item`), and a bare
    `barcode` would have been the only one of them that did not say where it came
    from. The prefix is this repository's grouping convention — `integration_*`,
    `batch_*` — so a listing keeps one provider's ledgers together.

    **One ledger per external operation, never one generic ledger.** The portal
    behind `mfds-food-safety-korea` carries five services and each one has its
    own natural key and its own column meanings: I2570 keys on 바코드번호,
    I1250 on 품목제조번호, I2510 on 품목코드, I2520 on 원재료코드, I2530 on
    시험항목코드. Folding them into one table forces a nullable column per
    foreign concept and a `source` discriminator on every query, which is a
    JSON blob wearing a schema (rule://backend-table-design, 1NF). So the four
    remaining services land as sibling ledgers with this same shape, and this
    table only holds what I2570 actually answers.

    **Rows join by natural key, not by foreign key.** `report_no` is what the
    품목보고 ledger (I1250) will key on, and the classification names are what
    the 품목분류 ledger (I2510) carries — but an external feed cannot promise
    referential integrity, so a barcode naming a report number nobody imported
    yet must still be storable. A `ForeignKey` would turn a normal ordering of
    two independent syncs into a failed batch.

    Two columns exist for the sync rather than for the business:

    - the unique `(barcode_no, report_no)` pair is the upsert target — the
      provider re-sends the same record on every overlapping window, and
      without the constraint each run would append a second copy;
    - `source_updated_at` is the provider's own 최종수정일시, which makes this
      table its own sync cursor: a completed pass hands its maximum to the next
      pass as `changed_date`, and the provider answers with rows dated on or
      after it (measured inclusive: `CHNG_DT=20150122` returns the rows dated
      2015-01-22, `20150123` returns none). On I2570 that currently selects
      everything — every sampled row carries the same 2015-01-22 — so the
      narrowing is latent, not active. It is nullable because the provider
      leaves the column empty on sparse records.
    """

    __tablename__ = "food_barcode"
    __table_args__ = (
        # 같은 바코드가 여러 품목제조번호로 등록될 수 있다 — 원장의 정체성은 그 쌍이다.
        UniqueConstraint("barcode_no", "report_no", name="uq_food_barcode_barcode_no_report_no"),
        Index("ix_food_barcode_report_no", "report_no"),
        Index("ix_food_barcode_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    barcode_no: Mapped[str] = mapped_column(String(32))
    report_no: Mapped[str] = mapped_column(String(50))
    # Provider free text: 200 rather than the usual 120 for a display name,
    # because a rejected INSERT would fail the whole page for one long name.
    report_item_name: Mapped[str | None] = mapped_column(String(200), default=None)
    product_name: Mapped[str | None] = mapped_column(String(200), default=None)
    company_name: Mapped[str | None] = mapped_column(String(200), default=None)
    upper_product_classification_name: Mapped[str | None] = mapped_column(String(120), default=None)
    top_product_classification_name: Mapped[str | None] = mapped_column(String(120), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
