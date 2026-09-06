# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


# ============================================================
# Constants
# ============================================================

# 식품안전나라 (`mfds-food-safety-korea`) is Korean and its 최종수정일시 carries no
# offset, so the reading is KST. Storing it as if it were UTC would move every
# record nine hours and make a sync cursor ask for a window it has already read.
SOURCE_TIMEZONE = ZoneInfo("Asia/Seoul")

# Measured on I2570: `2024-01-15 09:30:00.0`. The date-only forms are what the
# sibling services of the same portal answer with for the same column, so a
# ledger fed by any of them keeps a usable cursor instead of a null.
SOURCE_DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d")


# ============================================================
# Functions
# ============================================================


def source_text(value: object) -> str | None:
    """A provider string, or None for the empty ones it sends on sparse rows."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


def source_updated_at(value: object) -> datetime | None:
    """The provider's 최종수정일시 as a UTC timestamp, or None.

    Read as KST (the portal states no offset) and stored as UTC, because a
    database may hand the column back without its offset — SQLite does — and a
    naive value then needs one fixed reading.

    An unreadable stamp keeps the record: the column exists to move the sync
    cursor, and one row written in an unknown shape must not cost the page. That
    row is simply invisible to the high-water mark.

    Named after the portal, not after a domain: what these two functions know is
    one provider's wire dialect (`mfds-food-safety-korea`), and every ledger fed
    from it reads through them — `food_*` today, and whatever a later operation
    of the same portal fills. Called `food_source` it would have to be renamed or
    duplicated the first time a sibling domain arrived.

    Lives in `core/` rather than in a schema: the schema layer's surface is its
    Pydantic classes plus `to_read`/`to_read_list` (`check-backend-domain`), the
    same way `schemas/batch/schedule.py` reaches into `core.scheduler` for
    `validated_cron`. Copied per ledger it would be a second answer to "what
    timezone was that", the kind that drifts one ledger nine hours from its
    sibling.
    """
    text = source_text(value)
    if text is None:
        return None
    for pattern in SOURCE_DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(text, pattern)
        except ValueError:
            continue
        return parsed.replace(tzinfo=SOURCE_TIMEZONE).astimezone(UTC)
    return None
