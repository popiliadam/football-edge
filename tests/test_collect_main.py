"""main() sözleşmesi: çıkış kodları, temiz veritabanı, kaçan mühür, kredi bitişi."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from football_edge import collect
from tests.fake_db import FakeLedgerDb
from tests.payloads import event, quota_headers

LEAGUES_YAML = """
leagues:
  - id: good.1
    odds_api_key: soccer_good
    name: Good
    country: X
    lang: en
    gl: GB
    active: true
  - id: bad.1
    odds_api_key: soccer_bad
    name: Bad
    country: Y
    lang: en
    gl: GB
    active: true
"""

Handler = Callable[[httpx.Request], httpx.Response]


def _ok_handler(request: httpx.Request) -> httpx.Response:
    payload = [event("evt1", "2026-09-20T14:00:00Z")]
    return httpx.Response(200, json=payload, headers=quota_headers(400))


def _failing_bad_league(request: httpx.Request) -> httpx.Response:
    if "soccer_bad" in str(request.url):
        return httpx.Response(500, json={"message": "boom"})
    return _ok_handler(request)


def _quota_running_out(request: httpx.Request) -> httpx.Response:
    payload = [event("evt1", "2026-09-20T14:00:00Z")]
    return httpx.Response(200, json=payload, headers=quota_headers(3))


def _patch_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, db: FakeLedgerDb, handler: Handler
) -> None:
    leagues_path = tmp_path / "leagues.yaml"
    leagues_path.write_text(LEAGUES_YAML, encoding="utf-8")
    monkeypatch.setattr(collect, "LEAGUES_PATH", leagues_path)
    monkeypatch.setattr(collect, "connect", lambda: db)
    real_client = httpx.Client  # yama sonrası httpx.Client artık bu lambda olur
    monkeypatch.setattr(
        collect.httpx, "Client", lambda: real_client(transport=httpx.MockTransport(handler))
    )
    monkeypatch.setenv("ODDS_API_KEY", "TEST-KEY")


def test_main_writes_rows_on_a_clean_leagues_table(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E1: leagues tablosu boşken de yazmalı — elle kurulan ön koşul, ön koşul değildir."""
    db = FakeLedgerDb()
    _patch_main(monkeypatch, tmp_path, db, _ok_handler)

    code = collect.main(["snapshot"])

    assert db.snapshots, "temiz veritabanında hiç satır yazılmadı (yabancı anahtar arızası)"
    assert set(db.leagues) == {"good.1", "bad.1"}, "leagues tablosu konfigürasyondan doldurulmalı"
    assert code == 0
    assert "başarısız ligler" not in capsys.readouterr().out


def test_upsert_leagues_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E1: ikinci tur yine 2 lig bırakmalı; konfigürasyon kaynak, tablo ayna."""
    db = FakeLedgerDb()
    _patch_main(monkeypatch, tmp_path, db, _ok_handler)

    assert collect.main(["snapshot"]) == 0
    assert collect.main(["snapshot"]) == 0

    capsys.readouterr()
    assert len(db.leagues) == 2


def test_main_exits_3_and_isolates_the_failing_league(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E7: tek lig arızası exit 3 demeli ama diğer ligin satırlarını götürmemeli."""
    db = FakeLedgerDb()
    _patch_main(monkeypatch, tmp_path, db, _failing_bad_league)

    code = collect.main(["snapshot"])

    out = capsys.readouterr().out
    assert code == 3
    assert "başarısız ligler: bad.1" in out
    assert db.snapshots, "sağlam lig yine de yazılmalıydı"


def test_main_exits_2_and_reports_work_done_before_quota_ran_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E7+E8: kredi bitince exit 2, ama o ana kadar toplanan iş rapordan düşmemeli."""
    db = FakeLedgerDb()
    _patch_main(monkeypatch, tmp_path, db, _quota_running_out)

    code = collect.main(["snapshot"])

    out = capsys.readouterr().out
    assert code == 2
    assert "yazılan satır: 2" in out, f"kredi bitince yazılan iş kayboldu: {out!r}"
    assert len(db.snapshots) == 2


def test_main_reports_a_missed_seal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E3: başlama saati geçmiş mühürsüz maç sessizce kaybolmamalı."""
    now = datetime.now(UTC)
    db = FakeLedgerDb(
        leagues={"good.1": ("good.1",)},
        matches={
            "evt_past": {
                "league_id": "good.1",
                "commence_time": now - timedelta(hours=2),
                "sealed_at": None,
            }
        },
    )
    _patch_main(monkeypatch, tmp_path, db, _ok_handler)

    code = collect.main(["seal"])

    out = capsys.readouterr().out
    assert "kaçan mühür: evt_past" in out, f"kaçan mühür raporlanmadı: {out!r}"
    assert code == 0
