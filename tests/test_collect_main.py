"""main() sözleşmesi: çıkış kodları, temiz veritabanı, kaçan mühür, kredi bitişi."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from football_edge import collect
from football_edge.odds_api import Quota
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


# ── F4: kredi bitince arızalı ligler isimsiz kalıyordu ──────────────────────
# `_report` exit 2'yi `failed_leagues` dalından ÖNCE veriyordu: operatör hangi ligin
# ayrıca düştüğünü hiç öğrenemiyordu — bulgunun adını koyduğu zararın ta kendisi.

LEAGUES_YAML_THREE = """
leagues:
  - id: bad.1
    odds_api_key: soccer_bad
    name: Bad
    country: Y
    lang: en
    gl: GB
    active: true
  - id: good.1
    odds_api_key: soccer_good
    name: Good
    country: X
    lang: en
    gl: GB
    active: true
  - id: good.2
    odds_api_key: soccer_good_two
    name: Good Two
    country: Z
    lang: en
    gl: GB
    active: true
"""


def test_report_names_the_failed_leagues_even_when_credit_ran_out(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """F4: iki arıza aynı turda olabilir; ikisi de RAPORLANIR, sonra exit 2."""
    result = collect.CollectResult(
        written=2,
        quota=Quota(remaining=3, used=497, last_cost=1),
        failed_leagues=("bad.1",),
        quota_exhausted=True,
    )

    code = collect._report(result)

    out = capsys.readouterr().out
    assert "başarısız ligler: bad.1" in out, f"kredi bitince arızalı lig isimsiz kaldı: {out!r}"
    assert "kredi tükendi" in out
    assert code == 2, "kredi bitişi en ağır arızadır, çıkış kodu 2 kalmalı"


def test_main_names_both_the_failed_league_and_the_exhausted_credit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F4 uçtan uca: bad.1 düşer, good.1 krediyi tüketir, good.2 hiç denenmez."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "soccer_bad" in str(request.url):
            return httpx.Response(500, json={"message": "boom"})
        payload = [event("evt1", "2026-09-20T14:00:00Z")]
        return httpx.Response(200, json=payload, headers=quota_headers(3))

    db = FakeLedgerDb()
    _patch_main(monkeypatch, tmp_path, db, handler)
    (tmp_path / "leagues.yaml").write_text(LEAGUES_YAML_THREE, encoding="utf-8")

    code = collect.main(["snapshot"])

    out = capsys.readouterr().out
    assert code == 2
    assert "kredi tükendi" in out
    assert "başarısız ligler: bad.1" in out, f"arızalı lig kredi bitişinin altında kaldı: {out!r}"


def _seal_handler(now: datetime) -> Handler:
    """Mühür penceresinin İÇİNDE bir maç döndürür — kapanış satırı gerçekten yazılsın."""
    kickoff = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[event("evt1", kickoff)], headers=quota_headers(400))

    return handler


def _db_due_for_seal(now: datetime) -> FakeLedgerDb:
    return FakeLedgerDb(
        leagues={"good.1": ("good.1",)},
        matches={
            "evt1": {
                "league_id": "good.1",
                "commence_time": now + timedelta(minutes=10),
                "sealed_at": None,
            }
        },
    )


def test_main_spends_no_credit_when_the_league_mirror_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """G3: ayna düşünce her lig yine de ÜCRETLİ `fetch_odds`a gidiyordu.

    `upsert_matches` yabancı anahtarda patlayana kadar kredi çoktan harcanmış oluyordu:
    lig başına 1 kredi × 6 lig × 15 dakikalık mühür cron'u → 500 kredilik aylık ücretsiz
    katman iki günde biter. Ayna düşmüşse tur BAŞLAMADAN durur.

    F3'ün (round 2) kazanımı korunuyor: `main()` hâlâ traceback'le düşmez, arıza adıyla
    raporlanır, çıkış kodu 4'tür. Değişen tek şey, turun kredi harcamadan durması.
    """

    def exploding_upsert(conn: object, leagues: object) -> int:
        raise RuntimeError("leagues.odds_api_key UNIQUE ihlali")

    now = datetime.now(UTC)
    db = _db_due_for_seal(now)
    paid_calls: list[str] = []
    inner = _seal_handler(now)

    def counting_handler(request: httpx.Request) -> httpx.Response:
        paid_calls.append(str(request.url))
        return inner(request)

    _patch_main(monkeypatch, tmp_path, db, counting_handler)
    monkeypatch.setattr(collect, "upsert_leagues", exploding_upsert)

    code = collect.main(["seal"])

    out = capsys.readouterr().out
    assert paid_calls == [], f"ayna düşmüşken ücretli çağrı yapıldı: {paid_calls}"
    assert db.snapshots == [], "ayna düşmüşken satır yazılmamalı"
    assert db.matches["evt1"]["sealed_at"] is None, "satır yazılmadan mühür basılmamalı"
    assert "lig aynası tazelenemedi" in out, f"sessiz geçildi: {out!r}"
    assert code == 4, f"arıza raporlandı ama çıkış kodu sessiz kaldı: {code}"


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
