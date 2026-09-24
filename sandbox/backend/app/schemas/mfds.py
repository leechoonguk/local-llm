# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import BaseModel, BeforeValidator, ConfigDict


# ============================================================
# Constants
# ============================================================

# 식품의약품안전처 is Korean and its 최종수정일시 carries no offset, whichever
# gateway serves it, so the reading is KST. Stored as if it were UTC, every
# record would read nine hours off the portal's own page.
SOURCE_TIMEZONE = ZoneInfo("Asia/Seoul")

# Measured on I2570: `2024-01-15 09:30:00.0`. The date-only forms are what the
# sibling services answer with for the same column - `%Y-%m-%d` is the
# 영양성분DB through data.go.kr, `%Y%m%d` is I2520 - so a ledger fed by any of
# them keeps a usable stamp instead of a null.
SOURCE_DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d")


# ============================================================
# Classes
# ============================================================


class MfdsRecord(BaseModel):
    """What every ledger schema of the 식품안전나라 portal shares: one wire dialect.

    Named after the publisher, not after a gateway or a domain: what this
    module knows is how 식품의약품안전처 writes a record - the empty strings it
    sends on sparse rows, the clock its stamps are read on, the date-only forms
    some of its services answer with - and that is the same whether the record
    arrives from 식품안전나라 directly (`mfds-food-safety-korea`, ten ledgers) or
    through the 공공데이터포털 gateway (`data-go-kr`, the 영양성분DB - the
    `%Y-%m-%d` form below is that one's). Every ledger fed from either reads
    through the three types below, `food_*` today and whatever a later
    operation of the publisher fills. The knowledge is types rather than
    functions because a schema's surface is its classes: a field typed
    `MfdsText` is normalised on the way in, and `from_record` hands the raw
    `record.get("<key>")` over - which is also what `check-backend-ledger`
    reads to hold the mapping to the seeded contract.
    """

    model_config = ConfigDict(extra="forbid")

    @staticmethod
    def key_text(value: object) -> str | None:
        """A natural-key part of a record, or None when the record cannot be matched again.

        A record without it is dropped where it is read rather than becoming a
        row no later pass can find; every other refusal still raises, because
        that is a contract change and not a sparse record.
        """
        return _text(value)


# ============================================================
# Functions
# ============================================================


def _text(value: object) -> str | None:
    """A provider string, or None for the empty ones it sends on sparse rows."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _key_text(value: object) -> str:
    """A provider string that is part of a natural key: empty stays "", never None.

    A key column joins the stage to the ledger with `=`, and NULL never
    equals NULL - a row whose key had a NULL part would be inserted again
    on every pass. On I2580 (measured 2026-09-07) the serial repeats and
    `FNPRT_ITM_NM`/`ATTRB_SEQ` complete the key while being empty on 86% of
    the rows, so their emptiness is a key value, not a missing one.
    """
    if not isinstance(value, str):
        return ""
    return value.strip()


def _updated_at(value: object) -> object:
    """The provider's 최종수정일시 as a UTC timestamp, None for a stamp it cannot read.

    Read as KST (the portal states no offset) and stored as UTC, because a
    database may hand the column back without its offset - SQLite does - and
    a naive value then needs one fixed reading.

    An unreadable portal stamp keeps the record: the column is a reading of
    when the portal last touched the row (every pass walks the whole feed -
    nothing follows this column), and one row written in an unknown shape must
    not cost the page. That row simply shows no stamp. A value that is not a
    portal string - a datetime, an ISO string from the API - is left to the
    field's own parsing.
    """
    text = _text(value)
    if text is None:
        return None if isinstance(value, str) else value
    for pattern in SOURCE_DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(text, pattern)
        except ValueError:
            continue
        return parsed.replace(tzinfo=SOURCE_TIMEZONE).astimezone(UTC)
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


# A provider string, None when the portal sent an empty one.
MfdsText = Annotated[str | None, BeforeValidator(_text)]

# A provider string that completes a natural key: empty stays "", never None.
MfdsKeyText = Annotated[str, BeforeValidator(_key_text)]

# The portal's 최종수정일시, read on the portal's clock and stored as UTC.
MfdsDatetime = Annotated[datetime | None, BeforeValidator(_updated_at)]
