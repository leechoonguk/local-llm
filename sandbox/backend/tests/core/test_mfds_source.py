"""The wire conventions every ledger fed from 식품안전나라 reads through.

Two ledgers decode the same columns; these tests fix the readings so a change
to one cannot silently disagree with the other.
"""

from datetime import UTC, datetime

from app.core.mfds_source import source_text, source_updated_at


def test_source_text_reads_a_sparse_column_as_absent() -> None:
    """The portal sends empty and whitespace strings instead of omitting a field.

    Stored verbatim they would make `WHERE company_name IS NULL` miss rows that
    carry no company, and a ledger comparing a stored `""` against an incoming
    `"  "` would rewrite a row nothing changed about, every night.
    """
    assert source_text("  냉동김치 ") == "냉동김치"
    assert source_text("   ") is None
    assert source_text("") is None
    assert source_text(None) is None
    assert source_text(1234) is None


def test_source_updated_at_reads_the_portal_clock_as_kst() -> None:
    """The stamp carries no offset and the portal is Korean.

    Read as UTC it would move every record nine hours forward, and a sync
    cursor built from it would ask for a window the ledger has already read.
    """
    assert source_updated_at("2024-01-15 09:30:00.0") == datetime(2024, 1, 15, 0, 30, tzinfo=UTC)
    assert source_updated_at("2024-01-15 09:30:00") == datetime(2024, 1, 15, 0, 30, tzinfo=UTC)


def test_source_updated_at_reads_the_date_only_form_its_siblings_answer() -> None:
    """I2520 answers `YYYYMMDD` where I2570 answers a timestamp.

    One parser that knew only the timestamp form would answer "unknown" for a
    record that states its date, and the ledger's high-water mark would never
    move on the feed that uses it.
    """
    assert source_updated_at("20240115") == datetime(2024, 1, 14, 15, 0, tzinfo=UTC)
    assert source_updated_at("2024-01-15") == datetime(2024, 1, 14, 15, 0, tzinfo=UTC)


def test_source_updated_at_is_none_for_a_stamp_it_cannot_read() -> None:
    """An unreadable stamp costs the cursor, never the record.

    Raising here would drop a real item because of a formatting change; the
    caller stores the row and it is simply invisible to the high-water mark.
    """
    assert source_updated_at("어제") is None
    assert source_updated_at("") is None
    assert source_updated_at(20240115) is None
