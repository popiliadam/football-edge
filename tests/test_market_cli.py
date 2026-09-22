"""`python -m football_edge.market`: `efficiency` (önce kilit, sonra ölçüm) ve `bridge` (§8, §9)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge import collect
from football_edge.collect import EXIT_SOURCE_FAILED
from football_edge.collector import ContractViolation
from football_edge.history.catalog import Catalog
from football_edge.history.holdout import DEV, POST, HoldoutKey, select_periods
from football_edge.history.lock import HistoryLock, build_lock, dump_lock, load_lock, verify_lock
from football_edge.history.types import CLOSING, H2H, HistMatch
from football_edge.market import __main__ as market_main
from football_edge.market import efficiency
from football_edge.market.bridge import LiveClosing
from tests.efficiency_samples import BASE, EXTRA_LEAGUE, MAIN_LEAGUE, rich, synthetic
from tests.market_factory import hist_match

CATALOG = Catalog(current_season="2627", leagues=(MAIN_LEAGUE, EXTRA_LEAGUE))
History = Mapping[str, tuple[HistMatch, ...]]


class _Connection:
    """`with connect() as conn:` için en küçük bağlantı: CLI onu yalnız `load_matches`e verir."""

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _history() -> History:
    # Önbellekteki bütün dönemler: holdout satırları kilidin özetine girer, ölçüme hiç girmez.
    holdout = synthetic(8, start=date(2025, 8, 2), season="2526", first=200)
    extra = synthetic(56, league="X1", season="2023")
    return {"M1": (*rich(BASE), *rich(holdout)), "X1": extra}


def _wire(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, history: History, locked: History
) -> tuple[Path, list[Any]]:
    """Veritabanı, katalog ve günlük kurulumu sahte; kilit GERÇEK kilit koduyla dosyaya yazılır.

    Sahte `load_matches` Task 6'nın sözleşmesini (R96) izler: `lock` verilirse önce BÜTÜN satırlar
    üzerinde GERÇEK `verify_lock`, sonra yalnız DEV + POST döner (holdout anahtarsız çıkmaz).
    """
    calls: list[Any] = []
    connection = _Connection()

    def load(
        conn: object,
        catalog: Catalog,
        *,
        lock: HistoryLock | None = None,
        key: HoldoutKey | None = None,
    ) -> History:
        assert conn is connection and catalog is CATALOG and key is None
        calls.append(("load_matches", lock))
        if lock is not None:
            verify_lock(lock, history)
        periods = frozenset({DEV, POST})
        return {code: select_periods(rows, periods=periods) for code, rows in history.items()}

    monkeypatch.setattr(market_main, "configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(market_main, "connect", lambda: connection)
    monkeypatch.setattr(market_main, "load_catalog", lambda path: calls.append(path) or CATALOG)
    monkeypatch.setattr(market_main, "load_matches", load)
    lock_path = tmp_path / "history_lock.yaml"
    lock = build_lock(locked, locked_at=date(2026, 9, 29))
    lock_path.write_text(dump_lock(lock), encoding="utf-8")
    return lock_path, calls


def test_efficiency_writes_the_report_and_logs_a_one_line_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    history = _history()
    lock_path, calls = _wire(monkeypatch, tmp_path, history, history)
    seen: list[int] = []
    real = efficiency.league_efficiency

    def spy(league: Any, matches: Any, *, method: str, resamples: int) -> Any:
        seen.append(resamples)
        return real(league, matches, method=method, resamples=resamples)

    monkeypatch.setattr(market_main, "league_efficiency", spy)
    out = tmp_path / "reports" / "piyasa-verimliligi.md"
    caplog.set_level(logging.INFO, logger="football_edge.market")

    code = market_main.main(
        ["efficiency", "--out", str(out), "--lock", str(lock_path), "--catalog", "katalog.yaml"]
        + ["--resamples", "25"]
    )

    assert code == 0
    # kilit ayrı bir verify_lock çağrısıyla değil load_matches'in içinde doğrulanır (R96)
    assert calls == ["logging", Path("katalog.yaml"), ("load_matches", load_lock(lock_path))]
    assert seen == [25, 25]
    text = out.read_text(encoding="utf-8")
    assert "| M1 | m.1 | main | 56 |" in text  # sekiz holdout satırı N'ye girmedi
    assert "## Raporun ölçmedikleri" in text
    summary = [
        record.getMessage() for record in caplog.records if record.name == "football_edge.market"
    ]
    assert len(summary) == 1
    assert summary[0].startswith("verimlilik: 2 lig · yöntem=")
    assert str(out) in summary[0]


@pytest.mark.leakage
def test_efficiency_verifies_the_lock_before_computing_anything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    history = _history()
    stale = {**history, "M1": history["M1"][1:]}  # kilit bir satır eksik veriyle kurulmuş
    lock_path, _ = _wire(monkeypatch, tmp_path, history, stale)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("kilit doğrulanmadan ölçüm yapıldı")

    monkeypatch.setattr(market_main, "method_scores", forbidden)
    monkeypatch.setattr(market_main, "league_efficiency", forbidden)
    out = tmp_path / "rapor.md"

    code = market_main.main(["efficiency", "--out", str(out), "--lock", str(lock_path)])

    assert code == market_main.EXIT_LOCK_VIOLATION == 9
    assert not out.exists()
    assert "kilit doğrulanamadı" in caplog.text


@pytest.mark.leakage
@pytest.mark.parametrize("damage", ("yaml", "version"), ids=("bozuk-yaml", "surum-uyusmazligi"))
def test_a_corrupted_lock_file_exits_nine_before_the_cache_is_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, damage: str
) -> None:
    # R99: load_lock YAMALANMAZ — diske gerçekten bozuk bir kilit yazılır, gerçek okuyucu reddeder.
    history = _history()
    lock_path, calls = _wire(monkeypatch, tmp_path, history, history)
    if damage == "yaml":
        lock_path.write_text("canonical_version: 1\nleagues: [\n", encoding="utf-8")
    else:
        stale = replace(build_lock(history, locked_at=date(2026, 9, 29)), canonical_version=2)
        lock_path.write_text(dump_lock(stale), encoding="utf-8")
    out = tmp_path / "rapor.md"

    code = market_main.main(["efficiency", "--out", str(out), "--lock", str(lock_path)])

    assert code == market_main.EXIT_LOCK_VIOLATION
    assert not out.exists()
    assert [call for call in calls if isinstance(call, tuple)] == []  # önbellek hiç okunmadı


def test_efficiency_names_and_keeps_a_league_it_cannot_measure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # m9: AvgC 1X2'si tam maçı olmayan tek lig raporu düşürmez; satırı "—", logda adıyla anılır.
    bare = synthetic(56, league="X1", season="2023")
    history = {**_history(), "X1": tuple(replace(m, odds=MappingProxyType({})) for m in bare)}
    lock_path, _ = _wire(monkeypatch, tmp_path, history, history)
    out = tmp_path / "rapor.md"
    arguments = ["efficiency", "--out", str(out), "--lock", str(lock_path), "--resamples", "20"]

    code = market_main.main(arguments)

    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "| M1 | m.1 | main | 56 |" in text
    assert "| X1 | x.1 | extra | 0 | — |" in text
    assert "lig=X1 ölçülemedi" in caplog.text


def test_efficiency_stops_when_the_cache_breaks_its_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    history = _history()
    lock_path, _ = _wire(monkeypatch, tmp_path, history, history)

    def broken(conn: object, catalog: Catalog, **options: object) -> History:
        raise ContractViolation("football-data: önbellekte 3 dosya yok")

    monkeypatch.setattr(market_main, "load_matches", broken)
    out = tmp_path / "rapor.md"

    code = market_main.main(["efficiency", "--out", str(out), "--lock", str(lock_path)])

    assert code == EXIT_SOURCE_FAILED
    assert not out.exists()
    assert "önbellekte 3 dosya yok" in caplog.text


def test_efficiency_defaults_point_at_the_repository_config() -> None:
    args = market_main._parser().parse_args(["efficiency", "--out", "rapor.md"])
    assert args.lock == Path("config/history_lock.yaml")
    assert args.catalog == Path("config/history_leagues.yaml")
    assert args.resamples == 2000


def test_efficiency_requires_an_output_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(market_main, "configure_logging", lambda: None)
    with pytest.raises(SystemExit) as caught:
        market_main.main(["efficiency"])
    assert caught.value.code == 2


def test_market_exit_codes_do_not_collide_with_collect() -> None:
    taken = {value for name, value in vars(collect).items() if name.startswith("EXIT_")}
    ours = {market_main.EXIT_LOCK_VIOLATION, market_main.EXIT_NO_PAIRS}
    assert (market_main.EXIT_LOCK_VIOLATION, market_main.EXIT_NO_PAIRS) == (9, 10)
    assert not ours & (taken | {0, 1})


# ── bridge ───────────────────────────────────────────────────────────────────────────────────


def _live(match_id: str, home: str) -> LiveClosing:
    kickoff = datetime(2026, 9, 19, 14, 0, tzinfo=UTC)
    return LiveClosing(match_id, "m.1", kickoff, home, "Beta City", (2.0, 4.0, 4.0), 3)


def _post(home: str) -> HistMatch:
    """Sonrası dönemi (≥ 2026-07-01) tarihli sentetik football-data satırı."""
    avgc = {("Avg", H2H, CLOSING): (2.5, 10 / 3, 10 / 3)}
    return hist_match(league="M1", season="2627", day=date(2026, 9, 19), home=home, prices=avgc)


def _wire_bridge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, live: tuple[LiveClosing, ...]
) -> tuple[Path, list[Any]]:
    """Veritabanı sahte; takma ad dosyası gerçek: 'Delta Rovers United' → 'Delta Rov'.

    Dönen liste `load_catalog`un yolunu ve `load_live_closings`in `since`ini sırayla tutar.
    """
    connection = _Connection()
    seen: list[Any] = []

    def closings(conn: object, *, since: datetime) -> tuple[LiveClosing, ...]:
        assert conn is connection
        seen.append(since)
        return live

    history = {"M1": (_post("Alpha Town"), _post("Delta Rov")), "X1": ()}
    monkeypatch.setattr(market_main, "configure_logging", lambda: None)
    monkeypatch.setattr(market_main, "connect", lambda: connection)
    monkeypatch.setattr(market_main, "load_catalog", lambda path: seen.append(path) or CATALOG)
    monkeypatch.setattr(market_main, "load_matches", lambda conn, catalog: history)
    monkeypatch.setattr(market_main, "load_live_closings", closings)
    aliases = tmp_path / "history_aliases.yaml"
    aliases.write_text("aliases:\n  Delta Rovers United: Delta Rov\n", encoding="utf-8")
    return aliases, seen


def test_bridge_writes_the_report_with_the_days_n(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    live = (_live("m1", "Alpha Town"), _live("m2", "Delta Rovers United"), _live("m3", "Nobody"))
    aliases, seen = _wire_bridge(monkeypatch, tmp_path, live)
    out = tmp_path / "reports" / "kopru.md"
    caplog.set_level(logging.INFO, logger="football_edge.market")

    code = market_main.main(["bridge", "--out", str(out), "--aliases", str(aliases)])

    assert code == 0
    # varsayılanlar: depo kataloğu ve sonrası döneminin başı
    assert seen == [Path("config/history_leagues.yaml"), datetime(2026, 7, 1, tzinfo=UTC)]
    text = out.read_text(encoding="utf-8")
    assert "Karşılaştırılan maç (N): 2" in text  # takma adla eşlenen dahil
    assert "Karşılaştırılamayan canlı maç: 1" in text
    assert "Yöntem: shin" in text
    assert "Alpha Town" not in text
    summary = [
        record.getMessage() for record in caplog.records if record.name == "football_edge.market"
    ]
    assert summary == [f"köprü: n=2 · karşılaştırılamayan=1 · yöntem=shin · rapor={out}"]


def test_bridge_honours_catalog_since_and_method(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    aliases, seen = _wire_bridge(monkeypatch, tmp_path, (_live("m1", "Alpha Town"),))
    out = tmp_path / "kopru.md"
    arguments = ["bridge", "--out", str(out), "--aliases", str(aliases), "--catalog", "k.yaml"]

    code = market_main.main([*arguments, "--since", "2026-09-01", "--method", "multiplicative"])

    assert code == 0
    assert seen == [Path("k.yaml"), datetime(2026, 9, 1, tzinfo=UTC)]
    text = out.read_text(encoding="utf-8")
    assert "Yöntem: multiplicative" in text
    assert "2026-09-01 ve sonrasında" in text


def test_bridge_stops_when_the_cache_breaks_its_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    aliases, _ = _wire_bridge(monkeypatch, tmp_path, (_live("m1", "Alpha Town"),))

    def broken(conn: object, catalog: Catalog, **options: object) -> History:
        raise ContractViolation("football-data: önbellekte 3 dosya yok")

    monkeypatch.setattr(market_main, "load_matches", broken)
    out = tmp_path / "kopru.md"

    code = market_main.main(["bridge", "--out", str(out), "--aliases", str(aliases)])

    assert code == EXIT_SOURCE_FAILED
    assert not out.exists()


def test_bridge_without_comparable_pairs_writes_nothing_and_says_why(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    aliases, _ = _wire_bridge(monkeypatch, tmp_path, (_live("m3", "Nobody"),))
    out = tmp_path / "kopru.md"

    code = market_main.main(["bridge", "--out", str(out), "--aliases", str(aliases)])

    assert code == market_main.EXIT_NO_PAIRS
    assert not out.exists()
    assert "karşılaştırılabilir eşleşme yok" in caplog.text


def test_bridge_defaults_point_at_the_repository_config() -> None:
    args = market_main._parser().parse_args(["bridge", "--out", "kopru.md"])
    assert args.since == date(2026, 7, 1)
    assert args.catalog == Path("config/history_leagues.yaml")
    assert args.aliases == Path("config/history_aliases.yaml")
    assert args.method == "shin"
