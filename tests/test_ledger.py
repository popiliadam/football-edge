from __future__ import annotations

from typing import Any

from football_edge.ledger import GENESIS, canonical_timestamp, chain, row_hash, verify_chain

PAYLOADS: tuple[dict[str, Any], ...] = (
    {"event_id": "a", "bookmaker": "pinnacle", "price": 1.95},
    {"event_id": "a", "bookmaker": "betfair_ex_eu", "price": 1.97},
    {"event_id": "b", "bookmaker": "pinnacle", "price": 2.40},
)


def test_row_hash_is_deterministic() -> None:
    assert row_hash(GENESIS, PAYLOADS[0]) == row_hash(GENESIS, PAYLOADS[0])


def test_row_hash_ignores_key_order() -> None:
    reordered = {"price": 1.95, "bookmaker": "pinnacle", "event_id": "a"}
    assert row_hash(GENESIS, PAYLOADS[0]) == row_hash(GENESIS, reordered)


def test_row_hash_changes_with_content() -> None:
    altered = {**PAYLOADS[0], "price": 1.96}
    assert row_hash(GENESIS, PAYLOADS[0]) != row_hash(GENESIS, altered)


def test_row_hash_changes_with_prev_hash() -> None:
    assert row_hash(GENESIS, PAYLOADS[0]) != row_hash("f" * 64, PAYLOADS[0])


def test_chain_links_rows() -> None:
    rows = chain(PAYLOADS)
    assert rows[0]["prev_hash"] == GENESIS
    assert rows[1]["prev_hash"] == rows[0]["row_hash"]
    assert rows[2]["prev_hash"] == rows[1]["row_hash"]


def test_chain_does_not_mutate_input() -> None:
    original = {**PAYLOADS[0]}
    chain(PAYLOADS)
    assert PAYLOADS[0] == original
    assert "row_hash" not in PAYLOADS[0]


def test_verify_accepts_intact_chain() -> None:
    result = verify_chain(chain(PAYLOADS))
    assert result.ok is True
    assert result.checked == 3
    assert result.error is None


def test_verify_detects_edited_value() -> None:
    rows = list(chain(PAYLOADS))
    rows[1] = {**rows[1], "price": 9.99}
    result = verify_chain(tuple(rows))
    assert result.ok is False
    assert result.failed_index == 1
    assert "içerik" in (result.error or "")


def test_verify_detects_deleted_row() -> None:
    rows = chain(PAYLOADS)
    result = verify_chain((rows[0], rows[2]))
    assert result.ok is False
    assert result.failed_index == 1


def test_verify_resumes_from_known_head() -> None:
    first = chain(PAYLOADS[:2])
    head = first[-1]["row_hash"]
    second = chain(PAYLOADS[2:], prev_hash=head)
    assert verify_chain(second, start_hash=head).ok is True


def test_canonical_timestamp_is_symmetric_across_str_and_datetime() -> None:
    from datetime import UTC, datetime

    from football_edge.ledger import canonical_timestamp

    assert canonical_timestamp("2026-09-19T10:00:00Z") == canonical_timestamp(
        datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    )


def test_canonical_timestamp_preserves_microseconds() -> None:
    assert canonical_timestamp("2026-09-19T10:00:00.123456Z").endswith(".123456+00:00")
