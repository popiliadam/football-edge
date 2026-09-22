"""`python -m football_edge.backtest selftest`: önce kilit, sonra denetimler; çıkış kodları.

Veritabanı yok: bağlantı, `load_matches` ve denetimler sahte; sınanan, CLI'nin tutkalıdır. Kilit
dosyası GERÇEKTİR (R99): geçerlisi `dump_lock` ile yazılır, bozuğu diske bozuk yazılır —
`load_lock` hiçbir testte yamalanmaz.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge import collect
from football_edge.backtest import __main__ as cli
from football_edge.backtest.harness import ResultRecord
from football_edge.backtest.selftest import Check
from football_edge.backtest.strategies import EloPointInTime
from football_edge.history import __main__ as history_cli
from football_edge.history.catalog import EXTRA, MAIN, Catalog, HistoryLeague
from football_edge.history.holdout import HoldoutKey
from football_edge.history.lock import HistoryLock, LockViolation, build_lock, dump_lock, load_lock
from football_edge.history.types import HistMatch
from football_edge.market.devig import DEFAULT_METHOD

CATALOG = Catalog(
    current_season="2627",
    leagues=(
        HistoryLeague(
            code="E0",
            league_id="test.1",
            name="Test Ana",
            country="Ülke A",
            tier=1,
            kind=MAIN,
            first_season="0506",
            odds_api_key="",
        ),
        HistoryLeague(
            code="E1",
            league_id="test.2",
            name="Test Ana 2",
            country="Ülke A",
            tier=2,
            kind=MAIN,
            first_season="0506",
            odds_api_key="",
        ),
        HistoryLeague(
            code="BRA",
            league_id="test.3",
            name="Test Ek",
            country="Ülke B",
            tier=1,
            kind=EXTRA,
            first_season="",
            odds_api_key="",
        ),
    ),
)
GREEN = (Check("K1", True, True, "k1 ayrıntı"), Check("K2", False, False, "k2 ayrıntı"))
# Diske gerçekten bozuk yazılan kilitler (R99: bozuk YAML, sürüm uyuşmazlığı → LockViolation).
CORRUPTIONS: Mapping[str, Callable[[str], str]] = {
    "broken-yaml": lambda valid: "canonical_version: [1\n",
    "wrong-version": lambda valid: valid.replace("canonical_version: 1", "canonical_version: 99"),
}


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *exc: object) -> None:
        self.closed = True


@dataclass
class Calls:
    connection: FakeConnection = field(default_factory=FakeConnection)
    matches: Mapping[str, Sequence[HistMatch]] = field(default_factory=lambda: {"E0": ()})
    catalog_paths: list[Path] = field(default_factory=list)
    loaded_with: list[tuple[object, object, object, object]] = field(default_factory=list)
    selftest: list[dict[str, Any]] = field(default_factory=list)


def _lock_file(tmp_path: Path) -> Path:
    """Gerçek, geçerli bir kilit dosyası (lig yok): `load_lock` onu gerçekten okur."""
    path = tmp_path / "history_lock.yaml"
    path.write_text(dump_lock(build_lock({}, locked_at=date(2026, 9, 22))), encoding="utf-8")
    return path


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    checks: Sequence[Check] = GREEN,
    mismatch: bool = False,
) -> Calls:
    calls = Calls()

    def load_catalog(path: Path) -> Catalog:
        calls.catalog_paths.append(path)
        return CATALOG

    def load_matches(
        conn: object,
        catalog: Catalog,
        *,
        lock: HistoryLock | None = None,
        key: HoldoutKey | None = None,
    ) -> Mapping[str, Sequence[HistMatch]]:
        calls.loaded_with.append((conn, catalog, lock, key))
        if mismatch:
            raise LockViolation("E0/dev: beklenen 10 satır, gerçek 9")
        return calls.matches

    def run_selftest(
        matches: object, *, method: str, main_codes: frozenset[str], resamples: int
    ) -> tuple[Check, ...]:
        calls.selftest.append(
            {
                "matches": matches,
                "method": method,
                "main_codes": main_codes,
                "resamples": resamples,
                "connection_closed": calls.connection.closed,
            }
        )
        return tuple(checks)

    monkeypatch.setattr(cli, "connect", lambda: calls.connection)
    monkeypatch.setattr(cli, "load_catalog", load_catalog)
    monkeypatch.setattr(cli, "load_matches", load_matches)
    monkeypatch.setattr(cli, "run_selftest", run_selftest)
    return calls


def test_green_gate_checks_exit_zero_even_when_a_report_check_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _patch(monkeypatch)
    caplog.set_level(logging.INFO)

    assert cli.main(["selftest", "--lock", str(_lock_file(tmp_path))]) == 0
    assert "K1 (kapı) GEÇTİ — k1 ayrıntı" in caplog.messages
    assert "K2 (rapor) KALDI — k2 ayrıntı" in caplog.messages


def test_a_red_gate_check_exits_one_and_is_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _patch(monkeypatch, checks=(*GREEN, Check("K4", True, False, "k4 ayrıntı")))
    caplog.set_level(logging.INFO)

    assert cli.main(["selftest", "--lock", str(_lock_file(tmp_path))]) == cli.EXIT_GATE_FAILED == 1
    assert "K4 (kapı) KALDI — k4 ayrıntı" in caplog.messages
    assert "kırmızı kapı denetimi: K4" in caplog.messages


@pytest.mark.leakage
@pytest.mark.parametrize("corruption", sorted(CORRUPTIONS))
def test_a_corrupted_lock_file_exits_nine_before_the_database_is_touched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    corruption: str,
) -> None:
    calls = _patch(monkeypatch)
    lock = _lock_file(tmp_path)
    lock.write_text(CORRUPTIONS[corruption](lock.read_text(encoding="utf-8")), encoding="utf-8")

    assert cli.main(["selftest", "--lock", str(lock)]) == cli.EXIT_LOCK_VIOLATION == 9
    assert (calls.loaded_with, calls.selftest) == ([], [])
    assert any(message.startswith("kilit ihlali") for message in caplog.messages)


@pytest.mark.leakage
def test_a_lock_mismatch_found_by_load_matches_exits_nine_before_any_check_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    calls = _patch(monkeypatch, mismatch=True)

    assert cli.main(["selftest", "--lock", str(_lock_file(tmp_path))]) == 9
    assert calls.selftest == []
    assert any(
        message.startswith("kilit ihlali") and "E0/dev: beklenen 10 satır" in message
        for message in caplog.messages
    )


@pytest.mark.leakage
def test_load_matches_gets_the_loaded_lock_and_no_holdout_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R96: kilidi `load_matches` bütün satırlarda doğrular; CLI ayrıca doğrulamaz, anahtar da
    vermez (holdout açılmaz)."""
    calls = _patch(monkeypatch)
    lock = _lock_file(tmp_path)

    cli.main(["selftest", "--lock", str(lock)])

    assert calls.loaded_with == [(calls.connection, CATALOG, load_lock(lock), None)]
    assert calls.selftest[0]["matches"] is calls.matches


def test_main_leagues_method_and_resamples_reach_the_selftest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _patch(monkeypatch)

    cli.main(
        ["selftest", "--lock", str(_lock_file(tmp_path)), "--method", "power", "--resamples", "300"]
    )

    (call,) = calls.selftest
    assert (call["method"], call["resamples"]) == ("power", 300)
    assert call["main_codes"] == frozenset({"E0", "E1"})


def test_defaults_are_the_committed_lock_the_catalog_and_the_default_method() -> None:
    args = cli._parser().parse_args(["selftest"])

    assert (args.lock, args.catalog) == (
        Path("config/history_lock.yaml"),
        Path("config/history_leagues.yaml"),
    )
    assert (args.method, args.resamples) == (DEFAULT_METHOD, 2000)


def test_the_database_connection_is_closed_before_the_checks_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _patch(monkeypatch)

    cli.main(["selftest", "--lock", str(_lock_file(tmp_path))])

    assert calls.selftest[0]["connection_closed"] is True


def test_an_unknown_devig_method_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch(monkeypatch)

    with pytest.raises(SystemExit) as refused:
        cli.main(["selftest", "--method", "tahmin"])

    assert refused.value.code == 2
    assert calls.selftest == []


def test_the_redacting_log_setup_comes_before_anything_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bağlantı hatası DSN parolasını taşıyabilir: kök handler ondan ÖNCE sarılmış olmalı."""
    calls: list[str] = []

    def catalog(path: Path) -> Catalog:
        calls.append("catalog")
        raise RuntimeError("dur")

    monkeypatch.setattr(cli, "configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(cli, "load_catalog", catalog)

    with pytest.raises(RuntimeError, match="dur"):
        cli.main(["selftest"])
    assert calls == ["logging", "catalog"]


def test_rating_groups_are_the_catalog_countries() -> None:
    """R94: aynı ülkenin ligleri reytingi paylaşır (terfi); başka ülkenin aynı adlı kulübü değil."""
    groups = cli.rating_groups(CATALOG)

    assert dict(groups) == {"E0": "Ülke A", "E1": "Ülke A", "BRA": "Ülke B"}
    assert isinstance(groups, MappingProxyType)
    elo = EloPointInTime(groups=groups).observe(
        ResultRecord(
            league="E1",
            date=date(2024, 8, 3),
            home="Alfa",
            away="Beta",
            home_goals=2,
            away_goals=0,
            known_at=datetime(2024, 8, 3, 17, tzinfo=UTC),
        )
    )
    assert set(elo.ratings) == {("Ülke A", "Alfa"), ("Ülke A", "Beta")}


def test_a_lock_violation_has_the_same_code_as_in_the_history_cli() -> None:
    collectors = {
        value
        for name, value in vars(collect).items()
        if name.startswith("EXIT_") and isinstance(value, int)
    }

    assert cli.EXIT_LOCK_VIOLATION == history_cli.EXIT_LOCK_VIOLATION == 9
    assert cli.EXIT_LOCK_VIOLATION not in collectors | {0, 1}
    assert cli.EXIT_GATE_FAILED == 1
