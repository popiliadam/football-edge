"""`python -m football_edge.history` sözleşmesi: yollar, çıkış kodları, kilit, log kurulumu.

Kilit komutları GERÇEK yoldan koşar: sentetik dosyalar önce `sync --all` ile sahte veritabanına
senkronlanır; `lock --write` bütün dönemleri (`_load_all`), `lock --verify` `load_matches(lock=)`
üzerinden okur (R96). Hiçbir iç fonksiyon yamalanmaz.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest

from football_edge import collect
from football_edge.history import __main__ as cli
from football_edge.history.holdout import DEV, HOLDOUT
from football_edge.history.lock import load_lock
from tests.fake_hist_db import FakeHistDb
from tests.history_csv import MAIN_2526, csv_bytes, main_row
from tests.test_history_sync import CURRENT, EXTRA_FILE, FILES, OLD, Site

# 2024/25 ana lig dosyası geliştirme dönemi; OLD (2025/26) holdout, CURRENT (2026/27) sonrası, ek
# lig dosyası (FILES) holdout.
DEV_FILE = "/mmz4281/2425/E0.csv"
DEV_DAY, HOLDOUT_DAY = "17/08/2024", "16/08/2025"
CLI_FILES = {
    **FILES,
    DEV_FILE: csv_bytes(MAIN_2526, [main_row(n, {"Date": DEV_DAY}) for n in range(2)]),
}

CATALOG_YAML = """
current_season: "2627"
leagues:
  - {code: E0, league_id: eng.1, name: "Premier League", country: England, tier: 1, kind: main,
     first_season: "2425", odds_api_key: "soccer_epl"}
  - {code: BRA, league_id: bra.1, name: "Serie A", country: Brazil, tier: 1, kind: extra,
     first_season: "", odds_api_key: ""}
"""
SOURCES_YAML = """
sources:
  - id: football-data
    base_url: https://football-data.co.uk
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 0.0
    robots_verified_at: 2026-09-22
    declared_paths:
      - /mmz4281/2425/E0.csv
      - /mmz4281/2526/E0.csv
      - /mmz4281/2627/E0.csv
      - /new/BRA.csv
    enabled: true
    access_basis: robots
    terms_url: ''
    note: test
"""


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    site: Site,
    *,
    sources: str = SOURCES_YAML,
    robots: str = "User-agent: *\nDisallow:\n",
) -> FakeHistDb:
    (tmp_path / "catalog.yaml").write_text(CATALOG_YAML, encoding="utf-8")
    (tmp_path / "sources.yaml").write_text(sources, encoding="utf-8")
    (tmp_path / "robots").mkdir()
    (tmp_path / "robots/football-data.txt").write_text(robots, encoding="utf-8")
    monkeypatch.setattr(cli, "CATALOG_PATH", tmp_path / "catalog.yaml")
    monkeypatch.setattr(cli, "SOURCES_PATH", tmp_path / "sources.yaml")
    monkeypatch.setattr(cli, "ROBOTS_DIR", tmp_path / "robots")
    db = FakeHistDb()
    monkeypatch.setattr(cli, "connect", lambda: db)
    real_client = httpx.Client  # yama sonrası httpx.Client bu lambda olur
    monkeypatch.setattr(
        cli.httpx, "Client", lambda: real_client(transport=httpx.MockTransport(site))
    )
    return db


def test_sync_fetches_only_the_mutable_files_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    site = Site(CLI_FILES)
    _patch(monkeypatch, tmp_path, site)

    assert cli.main(["sync"]) == 0

    assert site.requested == [CURRENT, EXTRA_FILE]
    assert "2 yol istendi, 2 değişti, 0 aynı, 0 başarısız" in caplog.text


def test_sync_all_fetches_every_declared_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    site = Site(CLI_FILES)
    db = _patch(monkeypatch, tmp_path, site)

    assert cli.main(["sync", "--all"]) == 0

    assert site.requested == [DEV_FILE, OLD, CURRENT, EXTRA_FILE]
    assert set(db.files) == {DEV_FILE, OLD, CURRENT, EXTRA_FILE}


def test_a_failed_file_turns_the_run_red_with_the_source_code_and_its_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    _patch(monkeypatch, tmp_path, Site(CLI_FILES, status={CURRENT: 503}))

    assert cli.main(["sync"]) == collect.EXIT_SOURCE_FAILED

    assert f"başarısız: {CURRENT}" in caplog.text
    assert "1 başarısız" in caplog.text


def test_sync_asks_the_committed_robots_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CLI ayrıştırıcıyı ROBOTS_DIR'deki anlık görüntüden kurar; boş politika her yolu açardı."""
    site = Site(CLI_FILES)
    _patch(monkeypatch, tmp_path, site, robots="User-agent: *\nDisallow: /new/\n")

    assert cli.main(["sync"]) == collect.EXIT_SOURCE_FAILED

    assert site.requested == [CURRENT]
    assert EXTRA_FILE not in site.requested


def test_a_disabled_source_is_never_fetched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    site = Site(CLI_FILES)
    _patch(monkeypatch, tmp_path, site, sources=SOURCES_YAML.replace("true", "false"))

    with pytest.raises(RuntimeError, match="enabled=false"):
        cli.main(["sync"])
    assert site.requested == []


def test_the_redacting_log_setup_comes_before_anything_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bağlantı hatası DSN parolasını taşıyabilir: kök handler ondan ÖNCE sarılmış olmalı."""
    calls: list[str] = []

    def catalog(path: Path) -> None:
        calls.append("catalog")
        raise RuntimeError("dur")

    monkeypatch.setattr(cli, "configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(cli, "load_catalog", catalog)

    with pytest.raises(RuntimeError, match="dur"):
        cli.main(["sync"])
    assert calls == ["logging", "catalog"]


def test_the_lock_violation_code_is_its_own() -> None:
    taken = {value for name, value in vars(collect).items() if name.startswith("EXIT_")}

    assert cli.EXIT_LOCK_VIOLATION == 9
    assert cli.EXIT_LOCK_VIOLATION not in taken | {0, 1}


# ── lock ────────────────────────────────────────────────────────────────────


def _synced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Site, Path]:
    """Dört dosyayı senkronlar ve kilidi yazar; (site, kilit yolu) döner."""
    site = Site(CLI_FILES)
    _patch(monkeypatch, tmp_path, site)
    target = tmp_path / "history_lock.yaml"
    assert cli.main(["sync", "--all"]) == 0
    assert cli.main(["lock", "--write", str(target)]) == 0
    return site, target


def _rescored(path: str) -> bytes:
    """`path`in ilk maçının ev golü 2 → 3 (sonuç yine H): kilitli bir satır değişir."""
    day, count = {DEV_FILE: (DEV_DAY, 2), OLD: (HOLDOUT_DAY, 3)}[path]
    rows = [main_row(n, {"Date": day, "FTHG": "3" if n == 0 else "2"}) for n in range(count)]
    return csv_bytes(MAIN_2526, rows)


@pytest.mark.leakage
def test_lock_write_digests_every_period_and_verify_accepts_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`lock --write` holdout özetini de yazar (`_load_all`); `load_matches` holdout vermez."""
    _, target = _synced(monkeypatch, tmp_path)

    written = load_lock(target)

    assert (written.leagues["E0"][DEV].rows, written.leagues["E0"][HOLDOUT].rows) == (2, 3)
    assert (written.leagues["BRA"][DEV].rows, written.leagues["BRA"][HOLDOUT].rows) == (0, 2)
    assert cli.main(["lock", "--verify", str(target)]) == 0


@pytest.mark.leakage
@pytest.mark.parametrize("path", [DEV_FILE, OLD], ids=["gelistirme", "holdout"])
def test_lock_verify_exits_9_when_a_locked_row_changed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture, path: str
) -> None:
    """Holdout satırı dışarı hiç verilmez ama değişikliği yine kilide takılır (R96)."""
    site, target = _synced(monkeypatch, tmp_path)
    site.files = {**site.files, path: _rescored(path)}
    assert cli.main(["sync", "--all"]) == 0

    assert cli.main(["lock", "--verify", str(target)]) == cli.EXIT_LOCK_VIOLATION
    assert "KİLİT İHLALİ" in caplog.text


@pytest.mark.leakage
@pytest.mark.parametrize(
    "text", ["canonical_version: [\n", "canonical_version: 1\n"], ids=["bozuk-yaml", "eksik-alan"]
)
def test_a_broken_lock_file_exits_9_not_with_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture, text: str
) -> None:
    """R99: `load_lock` yapı hatasında LockViolation fırlatır; CLI onu da exit 9 ile karşılar."""
    _patch(monkeypatch, tmp_path, Site(CLI_FILES))
    target = tmp_path / "history_lock.yaml"
    target.write_text(text, encoding="utf-8")

    assert cli.main(["lock", "--verify", str(target)]) == cli.EXIT_LOCK_VIOLATION
    assert "KİLİT İHLALİ" in caplog.text


@pytest.mark.leakage
@pytest.mark.parametrize("flag", ["--write", "--verify"])
def test_lock_refuses_an_unusable_cache_with_the_source_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flag: str
) -> None:
    _, target = _synced(monkeypatch, tmp_path)
    before = target.read_text(encoding="utf-8")
    monkeypatch.setattr(cli, "connect", lambda: FakeHistDb())  # önbellek boş

    assert cli.main(["lock", flag, str(target)]) == collect.EXIT_SOURCE_FAILED
    assert target.read_text(encoding="utf-8") == before, "eksik önbellekle kilit yazıldı"
