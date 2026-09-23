"""Canlı gölge tahmin (Faz 3 tasarımı §10, R134) ve eşitlik raporu E3. Veritabanı yok; veri
SENTETİK (tests/model_builders.py) — canlı taraf aynı maçları defter biçiminde taşır."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.backtest.context import record_of
from football_edge.backtest.harness import replay
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.timeline import decision_at
from football_edge.backtest.walkforward import DC, ELO, MARKET, group_matches
from football_edge.history.catalog import MAIN
from football_edge.history.types import H2H, PRE_CLOSING
from football_edge.live import __main__ as live_cli
from football_edge.live.context import (
    LiveMatch,
    Quote,
    build_batch,
    match_key_text,
    naming_from,
)
from football_edge.live.report import outcomes_of
from football_edge.live.shadow import ShadowRow, rejected_prices, shadow_rows, write_shadow
from football_edge.market.devig import METHODS, POWER, devig
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModel, EloModelConfig
from tests.model_builders import season

GROUPS = MappingProxyType({"E0": "Ülke"})
KINDS = MappingProxyType({"E0": MAIN})
HISTORY = (
    *season("2526", datetime(2025, 8, 2).date(), seed=4),
    *season("2627", datetime(2026, 8, 1).date(), seed=5),
)
GROUP = group_matches({"E0": HISTORY}, GROUPS)["Ülke"]
NAMING = naming_from({"E0": HISTORY}, {"t.1": "E0"}, MappingProxyType({}))
CONFIG = ModelConfig("x", "c", "l", POWER, EloModelConfig(), DCConfig(min_matches=40), 7, 0.02, ())
SHA256 = "e" * 64
GIT = "f" * 40
# Σ 1/o ≈ 0,889 < 1: negatif marjlı kitabı hiçbir yöntem temizlemez (16i).
REJECTED = (3.0, 3.6, 3.6)


def _slot_matches(week_day: datetime) -> list[int]:
    return [index for index, m in enumerate(GROUP) if m.date == week_day.date()]


def _batch(
    indexes: list[int], prices: Mapping[int, tuple[float, ...]] = MappingProxyType({})
) -> Any:
    """`prices`: maç sırası → karar anı fiyatının yerine geçen 1X2 (yoksa tabanın `Avg`'i)."""
    live = [
        LiveMatch(f"id-{i}", "t.1", GROUP[i].kickoff, GROUP[i].home, GROUP[i].away) for i in indexes
    ]  # type: ignore[arg-type]
    decided = decision_at(GROUP[indexes[0]].date, GROUP[indexes[0]].kickoff)
    assert decided is not None
    quotes = [
        Quote(m.match_id, decided - timedelta(hours=4), "b1", "h2h", name, price)
        for m, i in zip(live, indexes, strict=True)
        for name, price in zip(
            (m.home, "Draw", m.away),
            prices.get(i, GROUP[i].prices("Avg", H2H, PRE_CLOSING) or ()),
            strict=True,
        )
    ]
    return build_batch(
        live,
        quotes,
        {"Ülke": GROUP},
        now=decided + timedelta(minutes=35),
        naming=NAMING,
        kinds=KINDS,
        rating_groups=GROUPS,
    )


def test_each_decided_match_gets_market_elo_and_dixon_coles_rows() -> None:
    indexes = _slot_matches(datetime(2026, 10, 3))
    batch = _batch(indexes)

    rows = shadow_rows(
        batch, config=CONFIG, rating_groups=GROUPS, config_sha256=SHA256, git_sha=GIT
    )

    assert len(batch.decisions) == len(indexes) == 4
    assert {(row.match_id, row.strategy) for row in rows} == {
        (f"id-{i}", name) for i in indexes for name in (DC, ELO, MARKET)
    }
    for row in rows:
        assert sum(row.probs) == pytest.approx(1.0)
        assert (row.model_config_sha256, row.git_sha) == (SHA256, GIT)


@pytest.mark.parametrize("method", METHODS)
def test_a_rejected_decision_price_writes_no_market_row_and_is_counted(method: str) -> None:
    """17g: karar anı fiyatını devig reddederse piyasa satırı yazılmaz — ama red SAYILIR (sessiz
    değil); Elo ve DC satırları yine yazılır, öteki maçlar etkilenmez."""
    indexes = _slot_matches(datetime(2026, 10, 3))
    batch = _batch(indexes, MappingProxyType({indexes[0]: REJECTED}))
    config = replace(CONFIG, method=method)

    rows = shadow_rows(
        batch, config=config, rating_groups=GROUPS, config_sha256=SHA256, git_sha=GIT
    )

    assert rejected_prices(batch, method) == 1
    assert {(row.match_id, row.strategy) for row in rows} == {
        (f"id-{i}", name) for i in indexes for name in (DC, ELO, MARKET)
    } - {(f"id-{indexes[0]}", MARKET)}
    assert {row.pre for row in rows if row.match_id == f"id-{indexes[0]}"} == {REJECTED}


def test_a_clean_batch_counts_no_rejected_price() -> None:
    assert rejected_prices(_batch(_slot_matches(datetime(2026, 10, 3))), POWER) == 0


@pytest.mark.leakage
def test_shadow_elo_equals_the_replayed_prediction() -> None:
    """E2'nin gölge yolu: grup başına bir kez kurulan durum harness'ın tahminini verir."""
    indexes = _slot_matches(datetime(2026, 10, 3))
    replayed = {
        p.match_index: p.probs
        for p in replay(GROUP, EloModel(config=CONFIG.elo, groups=GROUPS)).predictions
    }

    rows = shadow_rows(
        _batch(indexes), config=CONFIG, rating_groups=GROUPS, config_sha256=SHA256, git_sha=GIT
    )

    for row in rows:
        if row.strategy == ELO:
            index = int(row.match_id.removeprefix("id-"))
            assert row.probs == pytest.approx(replayed[index])


def test_the_market_row_is_the_devigged_pre_price() -> None:
    (index, *_) = _slot_matches(datetime(2026, 10, 3))
    rows = shadow_rows(
        _batch([index]), config=CONFIG, rating_groups=GROUPS, config_sha256=SHA256, git_sha=GIT
    )

    (market,) = [row for row in rows if row.strategy == MARKET]
    assert market.probs == pytest.approx(devig(market.pre, POWER))
    assert market.pre == GROUP[index].prices("Avg", H2H, PRE_CLOSING)


class _Cursor:
    def __init__(self, log: list[tuple[str, tuple[Any, ...]]], seen: set[tuple[Any, ...]]) -> None:
        self.log, self.seen, self.rowcount = log, seen, 0

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.log.append((sql, params))
        key = (params[0], params[2], params[10])
        self.rowcount = 0 if key in self.seen else 1
        self.seen.add(key)


class _Connection:
    def __init__(self) -> None:
        self.log: list[tuple[str, tuple[Any, ...]]] = []
        self.seen: set[tuple[Any, ...]] = set()
        self.commits = 0

    def cursor(self) -> _Cursor:
        return _Cursor(self.log, self.seen)

    def commit(self) -> None:
        self.commits += 1


def test_rows_are_written_once_per_match_strategy_and_config() -> None:
    row = ShadowRow(
        "m1",
        "E0|2026-10-03|Alfa|Beta",
        ELO,
        (0.5, 0.3, 0.2),
        (2.0, 3.3, 4.0),
        datetime(2026, 10, 2, 11, tzinfo=UTC),
        SHA256,
        GIT,
    )
    conn = _Connection()

    assert write_shadow(conn, (row, row, replace(row, strategy=DC))) == 2  # type: ignore[arg-type]
    assert conn.commits == 1
    sql, params = conn.log[0]
    assert "ON CONFLICT (match_id, strategy, model_config_sha256) DO NOTHING" in sql
    assert params == (
        "m1",
        row.match_key,
        ELO,
        0.5,
        0.3,
        0.2,
        2.0,
        3.3,
        4.0,
        row.decided_at,
        SHA256,
        GIT,
    )


def test_parity_pairs_live_matches_and_flags_a_shifted_kickoff() -> None:
    target = GROUP[-3]
    assert target.kickoff is not None
    good = LiveMatch("a", "t.1", target.kickoff, target.home.upper(), target.away)
    shifted = replace(good, match_id="b", kickoff=target.kickoff + timedelta(hours=1))
    stranger = LiveMatch("c", "t.1", target.kickoff, "Yok", target.away)

    report = live_cli.parity(
        [good, stranger], {"E0": HISTORY}, codes={"t.1": "E0"}, aliases={}, kinds=KINDS
    )
    bad = live_cli.parity([shifted], {"E0": HISTORY}, codes={"t.1": "E0"}, aliases={}, kinds=KINDS)

    assert (report.paired, report.unmatched, report.season_mismatch, report.kickoff_mismatch) == (
        1,
        1,
        0,
        0,
    )
    assert bad.kickoff_mismatch == 1


class _Session(_Connection):
    """`with connect() as conn` biçimi: `_shadow` bağlantıyı bağlam yöneticisi olarak açar."""

    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


@pytest.mark.leakage
def test_the_shadow_ledger_loads_a_day_beyond_the_staleness_lookback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """16f (B2): bayat koruması karara göre `LOOKBACK` geriye bakar; defter bir gün daha
    geriden yüklenmezse elle geç koşuda korumanın görmesi gereken maç yüklenmez."""
    windows: list[tuple[datetime, datetime]] = []

    def live_matches(conn: object, *, since: datetime, until: datetime) -> tuple[LiveMatch, ...]:
        windows.append((since, until))
        return ()

    monkeypatch.setattr(live_cli, "connect", _Session)
    monkeypatch.setattr(live_cli, "load_matches", lambda conn, catalog, **kwargs: {})
    monkeypatch.setattr(live_cli, "load_live_matches", live_matches)
    monkeypatch.setattr(live_cli, "load_quotes", lambda conn, ids, **kwargs: ())
    monkeypatch.setattr(live_cli, "head_sha", lambda: GIT)
    before = datetime.now(UTC)

    assert live_cli.main(["shadow"]) == 0

    ((since, until),) = windows
    assert until - since == live_cli.HORIZON + live_cli.LOOKBACK + timedelta(days=1)
    assert since <= before - live_cli.LOOKBACK - timedelta(days=1) + timedelta(minutes=1)


def test_the_shadow_match_key_joins_the_historical_result_of_the_same_match() -> None:
    """Gölge raporu sonucu tarihsel tabandan `match_key` ile bulur: `shadow_rows`un yazdığı anahtar
    ile `outcomes_of`un anahtarı aynı maç için AYNI yardımcıdan gelir (biçim iki yerde yazılmaz)."""
    (index, *_) = _slot_matches(datetime(2026, 10, 3))
    rows = shadow_rows(
        _batch([index]), config=CONFIG, rating_groups=GROUPS, config_sha256=SHA256, git_sha=GIT
    )

    keys = {row.match_key for row in rows}
    assert keys == {match_key_text(record_of(GROUP[index]).key)}
    assert keys <= set(outcomes_of({"E0": (GROUP[index],)}))
