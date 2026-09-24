"""The wire conventions every ledger fed from 식품안전나라 reads through.

Eleven ledgers decode the same columns through three types; these tests fix
the readings so a change to one cannot silently disagree with the other.
"""

from datetime import UTC, datetime

from pydantic import BaseModel

from app.schemas.mfds import MfdsDatetime, MfdsKeyText, MfdsRecord, MfdsText


class _Record(BaseModel):
    text: MfdsText = None
    key: MfdsKeyText = ""
    stamp: MfdsDatetime = None


def _stamp(wire: object) -> datetime | None:
    return _Record.model_validate({"stamp": wire}).stamp


def test_text_reads_a_sparse_column_as_absent() -> None:
    """The portal sends empty and whitespace strings instead of omitting a field.

    Stored verbatim they would make `WHERE company_name IS NULL` miss rows that
    carry no company, and a ledger comparing a stored `""` against an incoming
    `"  "` would rewrite a row nothing changed about, every night.
    """
    assert _Record.model_validate({"text": "  냉동김치 "}).text == "냉동김치"
    assert _Record.model_validate({"text": "   "}).text is None
    assert _Record.model_validate({"text": ""}).text is None
    assert _Record.model_validate({"text": None}).text is None
    assert _Record.model_validate({"text": 1234}).text is None
    assert MfdsRecord.key_text("  냉동김치 ") == "냉동김치"
    assert MfdsRecord.key_text("   ") is None


def test_key_text_keeps_an_empty_key_part_as_empty() -> None:
    """A key column joins with `=`, and NULL never equals NULL.

    On I2580 two key parts are empty on 86% of the rows (measured 2026-09-07);
    read as None they would insert every such row again on every pass.
    """
    assert _Record.model_validate({"key": " 제1항 "}).key == "제1항"
    assert _Record.model_validate({"key": "   "}).key == ""
    assert _Record.model_validate({"key": None}).key == ""


def test_stamp_reads_the_portal_clock_as_kst() -> None:
    """The stamp carries no offset and the portal is Korean.

    Read as UTC it would move every record nine hours forward, and a reader
    comparing the ledger against the portal's own page would see every row
    touched at a different hour.
    """
    assert _stamp("2024-01-15 09:30:00.0") == datetime(2024, 1, 15, 0, 30, tzinfo=UTC)
    assert _stamp("2024-01-15 09:30:00") == datetime(2024, 1, 15, 0, 30, tzinfo=UTC)


def test_stamp_reads_the_date_only_form_its_siblings_answer() -> None:
    """I2520 answers `YYYYMMDD` where I2570 answers a timestamp.

    One parser that knew only the timestamp form would answer "unknown" for a
    record that states its date, and every row of the feed that uses it would
    show no stamp.
    """
    assert _stamp("20240115") == datetime(2024, 1, 14, 15, 0, tzinfo=UTC)
    assert _stamp("2024-01-15") == datetime(2024, 1, 14, 15, 0, tzinfo=UTC)


def test_stamp_is_none_for_a_portal_stamp_it_cannot_read() -> None:
    """An unreadable stamp costs the stamp, never the record.

    Raising here would drop a real item because of a formatting change; the
    caller stores the row and it simply shows no stamp.
    """
    assert _stamp("어제") is None
    assert _stamp("") is None


def test_stamp_leaves_a_value_that_is_not_a_portal_string_to_the_field() -> None:
    """The same schema answers the API, whose clients send ISO 8601 and datetimes."""
    iso = _stamp("2024-01-15T09:30:00+09:00")
    assert iso == datetime(2024, 1, 15, 0, 30, tzinfo=UTC)
    given = datetime(2024, 1, 15, 0, 30, tzinfo=UTC)
    assert _Record(stamp=given).stamp == given
