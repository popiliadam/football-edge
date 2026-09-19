"""Mühür turu: pencere dışı maç kapanış fiyatı almamalı, kaçan mühür raporlanmalı."""

from __future__ import annotations

from collections.abc import Callable
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
    footystats_path="/good/xg",
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


# ── F1: mühür LİG değil MAÇ bazında basılır ─────────────────────────────────
# Lig "toplandı" sayılmak için HTTP çekiminin başarılı olması yetiyordu; o ligin
# penceredeki her maçı, hakkında tek satır yazılmamış olsa bile sealed_at alıyordu.
# Mühürlenen maç bir daha denenmez: kapanış fiyatı kalıcı olarak kaybolur.

POSTPONED = "2026-09-20T11:00:00Z"  # API'nin bildiği saat: pencerede DEĞİL


def _db_with(*match_ids: str) -> FakeLedgerDb:
    return FakeLedgerDb(
        leagues={"good.1": ("good.1",)},
        matches={
            match_id: _match(NOW + timedelta(minutes=10)) for match_id in ("evt_near", *match_ids)
        },
    )


def _run(db: FakeLedgerDb, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    run_seal(db, client, "KEY", (LEAGUE,), NOW)  # type: ignore[arg-type]


def _assert_only_recorded_match_is_sealed(db: FakeLedgerDb, unwritten: str) -> None:
    written = {row["match_id"] for row in db.snapshots}
    assert unwritten not in written, "önce satır yazılmış: senaryo kurgusu bozuk"
    assert db.matches["evt_near"]["sealed_at"] == NOW, "kaydı yazılan maç mühürlenmeliydi"
    assert db.matches[unwritten]["sealed_at"] is None, (
        f"{unwritten} hakkında tek satır yazılmadığı hâlde mühürlendi — kapanış fiyatı kayıp"
    )


def test_seal_does_not_stamp_a_match_whose_every_price_was_rejected() -> None:
    """F1(a): tüm fiyatları check (price > 1.0) ihlal eden maç kaydedilmedi; mühürlenmemeli."""

    def handler(request: httpx.Request) -> httpx.Response:
        payload = [event("evt_near", NEAR), event("evt_cheap", NEAR, prices=(1.0, 1.0))]
        return httpx.Response(200, json=payload, headers=quota_headers(400))

    db = _db_with("evt_cheap")
    _run(db, handler)

    _assert_only_recorded_match_is_sealed(db, "evt_cheap")


def test_seal_does_not_stamp_a_match_the_api_no_longer_quotes() -> None:
    """F1(c): piyasa askıya alındı, API olayı hiç döndürmedi — mühür basılamaz."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[event("evt_near", NEAR)], headers=quota_headers(400))

    db = _db_with("evt_gone")
    _run(db, handler)

    _assert_only_recorded_match_is_sealed(db, "evt_gone")


def test_seal_does_not_stamp_a_postponed_match_whose_db_time_is_stale() -> None:
    """F1(b): satır filtresi API saatine, UPDATE veritabanı saatine bakıyordu.

    `ON CONFLICT (id) DO NOTHING` maçın commence_time'ını hiç tazelemez: veritabanı
    maçı pencerede sanır (mühürler), API pencerede saymaz (tek satır yazılmaz).
    """

    def handler(request: httpx.Request) -> httpx.Response:
        payload = [event("evt_near", NEAR), event("evt_postponed", POSTPONED)]
        return httpx.Response(200, json=payload, headers=quota_headers(400))

    db = _db_with("evt_postponed")
    _run(db, handler)

    _assert_only_recorded_match_is_sealed(db, "evt_postponed")


# ── G1: mührü süren kimlik listesi COMMIT'TEN ÖNCE birikiyordu ───────────────
# `written` ataması `conn.commit()`ten bir satır ÖNCEDEYDİ. Commit, bağlantı AYAKTAYKEN
# de düşer (statement timeout, serialization abort, sunucu tarafı abort): `rollback()`
# başarılı olur, lig doğru biçimde arızalı sayılır, ama geri alınmış match_id'ler
# `written` içinde kalır, `written_matches`e akar ve `sealed_at` damgasını yer.
# Sonuç: kapanış satırı olmayan, bir daha hiç denenmeyecek bir maç — F1'in kapattığı
# hasarın aynısı, yalnız daha ince bir yerde.


def _commit_fails_once_rows_exist_for(match_id: str) -> Callable[[FakeLedgerDb], bool]:
    """Satırlar yazıldıktan SONRA, tam commit anında patlar."""

    def failing(db: FakeLedgerDb) -> bool:
        return any(row["match_id"] == match_id for row in db.snapshots)

    return failing


def test_seal_does_not_stamp_a_match_whose_commit_failed() -> None:
    """G1: commit düşerse satırlar gider — mühür o maça BASILAMAZ."""
    db = FakeLedgerDb(
        leagues={"good.1": ("good.1",)},
        matches={"evt_near": _match(NOW + timedelta(minutes=10))},
        commit_fails=_commit_fails_once_rows_exist_for("evt_near"),
    )
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    result = run_seal(db, client, "KEY", (LEAGUE,), NOW)  # type: ignore[arg-type]

    assert db.snapshots == [], "commit düştü: satırlar geri alınmış olmalıydı"
    assert db.matches["evt_near"]["sealed_at"] is None, (
        "commit'i düşen maç mühürlendi — kapanış satırı yok, maç bir daha denenmeyecek"
    )
    assert result.failed_leagues == ("good.1",), "commit'i düşen lig arızalı sayılmalı"
    assert result.written == 0, f"geri alınan satırlar yazılmış sayıldı: {result.written}"
