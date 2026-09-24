# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import CheckConstraint, Index, String, Text, UniqueConstraint, Uuid, and_
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.food.item_report import FoodItemReport


# ============================================================
# Constants
# ============================================================

# A digest key (`R…`/`F…` plus 16 hex characters) and the registry numbers it
# points at (12-15 digits, 16 at the widest on either registry).
CODE_LENGTH = 32

# The registry a product belongs to, in the vocabulary `food_item_report` owns:
# `domestic`, `livestock`, `import`, `health_functional` - 17 characters at the
# widest, so the bound is the same 32 that table uses.
KIND_LENGTH = 32

# What happened, in this table's own vocabulary - `inspection_failure` is 18
# characters, which is what the first live rebuild found against a 16-character
# column (2026-09-14), so the two vocabularies get two bounds.
RECORD_KIND_LENGTH = 32

# What kind of record it is. Three feeds publish about a product, and each is
# its own kind rather than a source column: a reader asks "was this recalled",
# not "which service said so". Two of them are **findings** (a specimen was
# collected and judged) and one is an **action** (a recall was ordered), which
# is why the table is named for both and `judgment` is null on the action.
RECALL_KIND = "recall"
INSPECTION_FAILURE_KIND = "inspection_failure"
COLLECTION_INSPECTION_KIND = "collection_inspection"
RECORD_KINDS = (RECALL_KIND, INSPECTION_FAILURE_KIND, COLLECTION_INSPECTION_KIND)

# `20260914` - the record's own date, normalised out of three different strings
# (I0490 writes a timestamp, I2620 writes "2026.03.11", I0460 writes 수거일자).
DATE_LENGTH = 20

# 판정결과, as 수거검사 publishes it: 적합 / 부적합 / 검토중 / 상기와같음, and
# empty where the verdict is not published yet. Null on a recall, which is an
# action and has no verdict of its own.
JUDGMENT_LENGTH = 120

# Our reading of that word, in three values a screen can switch on. The portal's
# own vocabulary is Korean and is what a reader sees; this is what a filter, a
# count and a colour are written against, so neither side has to translate the
# other. `상기와같음` reads as 적합 - it means "as above", and what is above is a
# verdict already published.
JUDGMENT_FAILED = "failed"
JUDGMENT_PASSED = "passed"
JUDGMENT_PENDING = "pending"
JUDGMENT_CODES = (JUDGMENT_FAILED, JUDGMENT_PASSED, JUDGMENT_PENDING)
JUDGMENT_CODE_LENGTH = 16

# The closed vocabularies these feeds pick from: 회수등급 4 자, 식품유형 42.
NAME_LENGTH = 120

NATURAL_KEY = ("record_key",)

# Everything else the derive job writes. Listed rather than read off the model,
# because the model is declared below this section and the list is what the
# derivation stages - a column added to one and missed in the other fails at
# the first rebuild instead of staying NULL.
SYNCED_COLUMNS = (
    "record_kind",
    "judgment",
    "judgment_code",
    "report_kind",
    "item_report_no",
    "recorded_on",
    "manufactured_text",
    "lot_date",
    "reason",
    "method",
    "grade",
    "test_item_name",
    "standard_text",
    "test_result_text",
    "institution_name",
    "product_name",
    "business_name",
    "product_type_name",
)


# ============================================================
# Classes
# ============================================================


class FoodSafetyRecord(Base, AuditMixin):
    """검사·조치 이력: every inspection of a product, and every action taken about it.

    Derived, not fed. Three ledgers, **whole**: `food_ledger_collection_inspection`
    (2,045,467 rows), `food_ledger_recall` (377) and
    `food_ledger_inspection_failure` (575), rewritten off all three every night.

    **A finding and an action are both records, and the difference is a column.**
    수거검사 publishes a verdict on a specimen (`judgment`: 적합 68.3 %, 공백
    21.1 %, 상기와같음 5.4 %, 검토중 4.7 %, 부적합 0.43 %); 회수 publishes an
    action and has no verdict. Keeping only the 부적합 was the table's first
    shape and it made two different things look the same on a screen: a product
    never sampled and a product sampled twelve times and clean both read
    "nothing published". 84,129 of our products carry an inspection; 1,867
    numbers carry a failure.

    **A record is not a declaration.** `food_item_report_declaration` holds the
    times a product was declared at the border - a fact of the product's own
    registry. This holds what a supervising authority found or did afterwards,
    which is why the two are separate tables rather than one with a kind column:
    a declaration has a 처리일자 and a 유통기한, a record has a verdict, a reason,
    a grade and a measurement.

    **The key is the record's digest, not the product's.** The publishers state a
    serial per record, but the serial spaces of the three feeds are unrelated,
    and a row whose 품목제조보고번호 is absent could not be keyed by the product
    at all. So `record_key` is `R`/`F`/`C` plus the SHA-256 prefix of the
    feed's own key columns, and it alone is unique - a composite key holding a
    nullable `item_report_no` would not dedupe, because Postgres lets NULLs
    repeat in a unique index.

    **Most records do not reach a product, and are kept anyway.** 1,378,492 of
    the 수거검사 rows carry no 품목제조보고번호 at all (농·수산물, 집단급식소
    수거), and 175,297 more carry one no registry here reports on. They are
    stored because this table is where the ledgers are read from, and they are
    **filtered at the read layer** (`FoodSafetyRecordRepository`, `mapped`),
    because a screen about products cannot draw a record that names none.
    """

    __tablename__ = "food_safety_record"
    __table_args__ = (
        UniqueConstraint("record_key", name="uq_food_safety_record_natural_key"),
        CheckConstraint(
            "record_kind IN ('recall', 'inspection_failure', 'collection_inspection')",
            name="ck_food_safety_record_kind",
        ),
        CheckConstraint(
            "judgment_code IS NULL OR judgment_code IN ('failed', 'passed', 'pending')",
            name="ck_food_safety_record_judgment_code",
        ),
        Index("ix_food_safety_record_report", "report_kind", "item_report_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    record_key: Mapped[str] = mapped_column(String(CODE_LENGTH))
    record_kind: Mapped[str] = mapped_column(String(RECORD_KIND_LENGTH), index=True)
    # What the inspection found. 적합 68.3 %, 공백 21.1 % (not published yet),
    # 상기와같음 5.4 %, 검토중 4.7 %, 부적합 0.43 % over the whole 수거검사 feed -
    # so the column is what tells a clean record from a hazard, and the screens
    # narrow on it rather than on the kind.
    judgment: Mapped[str | None] = mapped_column(String(JUDGMENT_LENGTH), default=None)
    # The same verdict as a code this codebase owns, because the portal's word is
    # Korean data: a screen colours and counts by this, and shows `judgment`.
    judgment_code: Mapped[str | None] = mapped_column(
        String(JUDGMENT_CODE_LENGTH), default=None, index=True
    )
    # Which registry the product is in, decided by looking the number up: it is
    # in I1250 or it is in C006, and the two number their reports in separate
    # spaces (measured 2026-09-08: no C006 number is in I1250). A number the
    # derivation cannot find in either leaves both columns as the feed had them -
    # the number is kept, the kind is NULL, because guessing a registry from the
    # shape of a number would put a fact in a column that nothing measured.
    report_kind: Mapped[str | None] = mapped_column(String(KIND_LENGTH), default=None)
    item_report_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    # The day the registry recorded the event: I0490's 등록일시 to the date,
    # I2620's "2026.03.11" undotted. 376 of 376 and 572 of 572 carry one.
    recorded_on: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None, index=True)
    # 제조일자 as printed, which is not a date on either feed ("데이터없음",
    # "(포장일자) 2026.4.2"), so it is kept as the text it is.
    manufactured_text: Mapped[str | None] = mapped_column(Text, default=None)
    # The same, read as a date where one can be read: `20260526` out of
    # "(포장일자) 2026.5.26" or "2026. 7. 23.(포장일자)". This is the lot the
    # authority acted on, and on an import it is the declaration's own key -
    # the portal shows the recall on one 수입신고 of six for the same product
    # (measured 2026-09-20, rcno 202600444218), and that declaration's 소비기한
    # starts on this day. So `(item_report_no, lot_date)` reaches the
    # declaration row at read time; nothing else is stored for it. NULL where
    # the feed printed no date ("데이터없음", "-", a range): 46 of 80 unmapped
    # recalls carry none, and a guess would put an event on a lot that was
    # never named.
    lot_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    # What the event says, in the words of whichever feed said it: the recall's
    # reason, method and grade; the inspection's item, standard, result and
    # institution. A column of one feed is NULL on the other's rows.
    reason: Mapped[str | None] = mapped_column(Text, default=None)
    method: Mapped[str | None] = mapped_column(Text, default=None)
    grade: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    test_item_name: Mapped[str | None] = mapped_column(Text, default=None)
    standard_text: Mapped[str | None] = mapped_column(Text, default=None)
    test_result_text: Mapped[str | None] = mapped_column(Text, default=None)
    institution_name: Mapped[str | None] = mapped_column(Text, default=None)
    # What the feed says the product and its business are. Repeated here rather
    # than reached through `item_report_no`, because most events never reach a
    # product row and a screen still has to name what was recalled.
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)

    # The product this event is about, where the number reached one: 147 of 174
    # recall numbers and 57 of 70 inspection numbers resolve (2026-09-14).
    # `viewonly`, because the derive job writes both tables and a relationship
    # that could write would be a second writer (rule://backend-relations).
    item_report: Mapped[FoodItemReport | None] = relationship(
        primaryjoin=lambda: and_(
            foreign(FoodSafetyRecord.report_kind) == FoodItemReport.report_kind,
            foreign(FoodSafetyRecord.item_report_no) == FoodItemReport.item_report_no,
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
