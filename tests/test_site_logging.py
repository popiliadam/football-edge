"""Site komutlarının logu (§5.1, RUNBOOK §3.8): public log yalnız sayı ve hash taşır.

Depo ve Actions logları herkese açık. `SITE_DATABASE_URL` kök handler'da redakte edilir; girdi
dökümü (kitap bazında fiyat) ne loga ne diske gider; çöken ikinci türetimin çıktısı aktarılmaz.
"""

from __future__ import annotations

import io
import logging
import re
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
import pytest

from football_edge import collect
from football_edge.site import __main__ as site_main
from football_edge.site.contract import EXIT_SITE_CONFIG, EXIT_SITE_NONDETERMINISTIC
from football_edge.site.export import ExportRefused, derive_in_subprocess
from tests.fake_site_db import FakeSiteDb
from tests.site_builders import EVEN, Round, anchored_repo, at, export_dump, ledger, payloads

REPO = Path(__file__).resolve().parent.parent
DSN_VAR = "SITE_DATABASE" + "_URL"
PASSWORD = "sahte-site-parolasi"
DSN = f"postgresql://site_reader.sahteref:{PASSWORD}@db.sahte.invalid:5432/postgres"
M1 = "01" + "ab" * 15


@contextmanager
def _captured_root() -> Iterator[io.StringIO]:
    """Kökü pytest'in handler'larından arındırıp `configure_logging`in kurduğunu yakalar."""
    root = logging.getLogger()
    saved, hook = root.handlers[:], sys.excepthook
    for handler in saved:
        root.removeHandler(handler)
    stream = io.StringIO()
    try:
        collect.configure_logging(stream)
        yield stream
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        for handler in saved:
            root.addHandler(handler)
        sys.excepthook = hook


def test_the_site_dsn_and_its_password_are_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DSN_VAR, DSN)
    with _captured_root() as stream:
        logging.getLogger("football_edge.site").warning("bağlantı: %s / %s", DSN, PASSWORD)

    assert PASSWORD not in stream.getvalue() and "db.sahte.invalid" not in stream.getvalue()


def test_export_without_the_secret_names_it_and_publishes_nothing(tmp_path: Path) -> None:
    env = {"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, "-m", "football_edge.site", "export", "--out", str(tmp_path / "out")],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=env,
        check=False,
    )

    assert result.returncode == EXIT_SITE_CONFIG
    assert "SITE_DATABASE_URL yok — yayın yapılmadı" in result.stdout
    assert not (tmp_path / "out").exists()


def test_both_public_commands_configure_redacted_logging(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(site_main, "configure_logging", lambda: calls.append("log"))
    monkeypatch.delenv(DSN_VAR, raising=False)

    site_main.main(["export", "--out", str(tmp_path / "out")])
    site_main.main(["verify-snapshot", str(REPO / "web/fixtures/snapshot.fixture.json")])

    assert calls == ["log", "log"]


def test_a_successful_export_logs_counts_and_hashes_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rounds = [Round(M1, "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3)]
    rows = ledger(payloads(rounds))
    db = FakeSiteDb(
        leagues=[("tst.1", "Deneme Ligi", "Testland", True)],
        matches=[(M1, "tst.1", at("2026-09-22T14:00:00Z"), "Alfa Spor", "Beta FK")],
        ledger=rows,
    )
    anchors = anchored_repo(
        tmp_path / "repo", rows=3, last_id=3, head=rows[2]["row_hash"], day="2026-09-21"
    )
    real_export = site_main.run_export

    def run(conn: Any, out: Path, **options: Any) -> Any:
        chosen = {**options, "anchor_dir": anchors, "league_slugs": {"tst.1": "deneme-ligi"}}
        return real_export(db, out, **chosen)  # type: ignore[arg-type]

    monkeypatch.setenv(DSN_VAR, DSN)
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))
    monkeypatch.setenv("GITHUB_SHA", "1" * 40)
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(site_main, "connect", lambda dsn: _Closing())
    monkeypatch.setattr(site_main, "run_export", run)
    monkeypatch.setattr(site_main, "configure_logging", lambda: None)
    with _captured_root() as stream:
        code = site_main.main(["export", "--out", str(tmp_path / "out")])

    text = stream.getvalue()
    assert code == 0, text
    assert "maç=1 lig=1 takım=2 satır=9 last_id=9" in text
    assert re.search(r"\b\d+\.\d+\b", text.split(" INFO ", 1)[1]) is None, "fiyat benzeri sayı"
    assert "Alfa Spor" not in text and PASSWORD not in text
    written = sorted(
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )
    assert written == [
        "out/snapshot.json",
        "out/snapshot.sha256",
        "repo/ledger/head-2026-09-21.txt",
    ]


class _Closing:
    def __enter__(self) -> _Closing:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_a_crashing_second_derivation_relays_no_price(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """n4: çocuğa fiyat içeren bir istisna attırılır; loga giden çıktıda fiyat yok."""
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))
    rounds = [Round(M1, "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3)]
    dump = export_dump(
        leagues=[("tst.1", "Deneme Ligi", "Testland", "deneme-ligi")],
        matches=[(M1, "tst.1", "2026-09-22T14:00:00Z", "Alfa Spor", "Beta FK")],
        rounds=rounds,
    ).replace('"4.0"', '"4.47x"', 1)

    with _captured_root() as stream:
        with pytest.raises(ExportRefused) as refused:
            derive_in_subprocess(dump, hash_seed="1")
        logging.getLogger("football_edge.site").error("%s", refused.value)

    seen = stream.getvalue() + "".join(capsys.readouterr())
    assert refused.value.code == EXIT_SITE_NONDETERMINISTIC
    assert "4.47" not in seen and "Traceback" not in seen


def test_a_database_error_is_named_by_class_and_its_text_is_not_printed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """m6: libpq hatası adresin parçasını taşıyabilir; CLI yalnız sınıf adını basar, exit 20."""

    def refuse(dsn: str) -> Any:
        raise psycopg.OperationalError(f"bağlanılamadı: {PASSWORD}@db.sahte.invalid")

    monkeypatch.setenv(DSN_VAR, DSN)
    monkeypatch.setenv("GITHUB_SHA", "1" * 40)
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(site_main, "connect", refuse)
    monkeypatch.setattr(site_main, "configure_logging", lambda: None)

    code = site_main.main(["export", "--out", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert code == EXIT_SITE_CONFIG
    assert "DIŞA AKTARIM REDDEDİLDİ: veritabanı hatası (OperationalError)" in out
    assert PASSWORD not in out and "sahte.invalid" not in out


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (None, "FileNotFoundError"),
        ("version: 1\nleague_slugs:\n  a.1: ayni\n  b.1: ayni\n", "aynı slug"),
        ("version: 1\nleague_slugs: [\n", "ParserError"),
    ],
)
def test_a_missing_or_malformed_league_slug_file_is_a_named_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    content: str | None,
    reason: str,
) -> None:
    """N3: bozuk ya da eksik `config/site_leagues.yaml` exit 1 + traceback değil, exit 20 + adı."""
    slugs = tmp_path / "site_leagues.yaml"
    if content is not None:
        slugs.write_text(content, encoding="utf-8")
    monkeypatch.setenv(DSN_VAR, DSN)
    monkeypatch.setenv("GITHUB_SHA", "1" * 40)
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(site_main, "SITE_LEAGUES_PATH", slugs)
    monkeypatch.setattr(site_main, "configure_logging", lambda: None)

    code = site_main.main(["export", "--out", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert code == EXIT_SITE_CONFIG
    assert "DIŞA AKTARIM REDDEDİLDİ" in out and "lig slug'ları okunamadı" in out and reason in out
    assert not (tmp_path / "out").exists()
