"""Mühür turu: pencere dışı maç kapanış fiyatı almamalı, kaçan mühür raporlanmalı."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from football_edge.collect import run_seal
from football_edge.leagues import League
from tests.fake_db import FakeLedgerDb
from tests.payloads import event, quota_headers

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
NEAR = "2026-09-19T12:10:00Z"  # 10 dakika sonra — mühür penceresinde
FAR = "2026-09-20T11:00:00Z"  # 23 saat sonra — pencerede DEĞİL, ama 24 saatlik çekimde
LEAGUE = League(
    id="good.1",
    odds_api_key="soccer_good",
    name="Good",
    country="X",
    lang="en",
    gl="GB",
    active=True,
)


def _handler(request: httpx.Request) -> httpx.Response:
    payload = [event("evt_near", NEAR), event("evt_far", FAR)]
    return httpx.Response(200, json=payload, headers=quota_headers(400))


def _match(commence_time: datetime) -> dict[str, object]:
    return {"league_id": "good.1", "commence_time": commence_time, "sealed_at": None}


def _db_with_both_matches() -> FakeLedgerDb:
    return FakeLedgerDb(
        leagues={"good.1": ("good.1",)},
        matches={
            "evt_near": _match(NOW + timedelta(minutes=10)),
            "evt_far": _match(NOW + timedelta(hours=23)),
        },
    )


def test_seal_does_not_stamp_a_match_outside_the_window() -> None:
    """E2: 24 saatlik çekimin tamamı 'kapanış' diye yazılırsa ürünün ölçtüğü şey bozulur."""
    db = _db_with_both_matches()
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    run_seal(db, client, "KEY", (LEAGUE,), NOW)  # type: ignore[arg-type]

    closing = {row["match_id"] for row in db.snapshots if row["is_closing"]}
    assert closing == {"evt_near"}, f"pencere dışı maç kapanış damgası aldı: {closing}"


def test_seal_writes_nothing_at_all_for_a_match_outside_the_window() -> None:
    db = _db_with_both_matches()
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    run_seal(db, client, "KEY", (LEAGUE,), NOW)  # type: ignore[arg-type]

    assert all(row["match_id"] == "evt_near" for row in db.snapshots)


def test_seal_stamps_sealed_at_only_for_the_windowed_match() -> None:
    db = _db_with_both_matches()
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    run_seal(db, client, "KEY", (LEAGUE,), NOW)  # type: ignore[arg-type]

    assert db.matches["evt_near"]["sealed_at"] == NOW
    assert db.matches["evt_far"]["sealed_at"] is None


def test_seal_reports_a_match_whose_kickoff_already_passed() -> None:
    """E3: cron kayarsa maç mühürsüz kalır; sessizce exit 0 demek arızayı gizler."""
    db = FakeLedgerDb(
        leagues={"good.1": ("good.1",)},
        matches={"evt_past": _match(NOW - timedelta(hours=2))},
    )
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    result = run_seal(db, client, "KEY", (LEAGUE,), NOW)  # type: ignore[arg-type]

    assert result.missed_seals == ("evt_past",)


def test_seal_does_not_report_a_match_still_ahead_as_missed() -> None:
    db = _db_with_both_matches()
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    result = run_seal(db, client, "KEY", (LEAGUE,), NOW)  # type: ignore[arg-type]

    assert result.missed_seals == ()
