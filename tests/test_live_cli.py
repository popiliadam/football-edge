"""`python -m football_edge.live {shadow,parity}` tutkalı sahte `connect` ile (16l).

Veritabanı yok: bağlantı, okuyucular ve saat yamalanır; `build_batch`, `shadow_rows`,
`write_shadow` ve `parity` GERÇEKTİR. Veri SENTETİK (tests/model_builders.py)."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.backtest.model_config import ModelConfig, file_sha256
from football_edge.backtest.timeline import decision_at
from football_edge.history.catalog import MAIN, Catalog, HistoryLeague
from football_edge.history.lock import EXIT_LOCK_VIOLATION, LockViolation
from football_edge.history.types import H2H, PRE_CLOSING, HistMatch
from football_edge.live import __main__ as live_cli
from football_edge.live.context import LiveMatch, Quote
from football_edge.market.devig import POWER, SHIN
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModelConfig
from tests.model_builders import season

HISTORY = (
    *season("2526", date(2025, 8, 2), seed=4),
    *season("2627", date(2026, 8, 1), seed=5),
)
CATALOG = Catalog("2627", (HistoryLeague("E0", "t.1", "Test", "Ülke", 1, MAIN, "1112", ""),))
SLOT = tuple(m for m in HISTORY if m.date == date(2026, 10, 3))
DECIDED = decision_at(SLOT[0].date, SLOT[0].kickoff)
assert DECIDED is not None
NOW = DECIDED + timedelta(minutes=35)


def _live(match: HistMatch, index: int) -> LiveMatch:
    assert match.kickoff is not None
    return LiveMatch(f"id-{index}", "t.1", match.kickoff, match.home, match.away)


LIVE = tuple(_live(match, index) for index, match in enumerate(SLOT))
QUOTES = tuple(
    Quote(live.match_id, DECIDED - timedelta(hours=4), "b1", "h2h", name, price)
    for live, match in zip(LIVE, SLOT, strict=True)
    for name, price in zip(
        (live.home, "Draw", live.away), match.prices("Avg", H2H, PRE_CLOSING) or (), strict=True
    )
)


class _Clock(datetime):
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> _Clock:
        return cls.fromtimestamp(NOW.timestamp(), tz)


class _Cursor:
    def __init__(self, db: _Db) -> None:
        self.db, self.rowcount = db, 0

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.db.inserts.append(params)
        self.rowcount = 1


class _Db:
    """`connect()` → bağlam yöneticisi; `write_shadow`un gördüğü tek yazma yolu `cursor`dır."""

    def __init__(self) -> None:
        self.connects = 0
        self.inserts: list[tuple[Any, ...]] = []
        self.commits = 0

    def __call__(self) -> _Db:
        self.connects += 1
        return self

    def __enter__(self) -> _Db:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        self.commits += 1


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    tmp: Path,
    db: _Db,
    *,
    live: tuple[LiveMatch, ...] = LIVE,
    quotes: tuple[Quote, ...] = QUOTES,
    lock_error: bool = False,
    method: str = POWER,
) -> list[str]:
    """Yamalar; dönen liste yapılandırma dosyalarının CLI argümanlarıdır."""
    for name in ("catalog", "lock", "config", "aliases"):
        (tmp / f"{name}.yaml").write_text(f"{name}\n", encoding="utf-8")
    config = ModelConfig(
        "2026-10-01",
        file_sha256(tmp / "catalog.yaml"),
        file_sha256(tmp / "lock.yaml"),
        method,
        EloModelConfig(),
        DCConfig(min_matches=40),
        7,
        0.02,
        (),
    )

    def load_matches(conn: object, catalog: object, *, lock: object = None) -> object:
        if lock_error:
            raise LockViolation("E0/holdout: fark")
        return {"E0": HISTORY}

    monkeypatch.setattr(live_cli, "connect", db)
    monkeypatch.setattr(live_cli, "datetime", _Clock)
    monkeypatch.setattr(live_cli, "load_model_config", lambda path: config)
    monkeypatch.setattr(live_cli, "load_catalog", lambda path: CATALOG)
    monkeypatch.setattr(live_cli, "load_lock", lambda path: object())
    monkeypatch.setattr(live_cli, "load_aliases", lambda path: MappingProxyType({}))
    monkeypatch.setattr(live_cli, "load_matches", load_matches)
    monkeypatch.setattr(live_cli, "load_live_matches", lambda conn, **window: list(live))
    monkeypatch.setattr(live_cli, "load_quotes", lambda conn, ids, **window: list(quotes))
    monkeypatch.setattr(live_cli, "head_sha", lambda: "f" * 40)
    return [
        *("--config", str(tmp / "config.yaml")),
        *("--catalog", str(tmp / "catalog.yaml")),
        *("--lock", str(tmp / "lock.yaml")),
        *("--aliases", str(tmp / "aliases.yaml")),
    ]


def test_shadow_writes_every_decided_match_through_one_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db()
    files = _patch(monkeypatch, tmp_path, db)

    code = live_cli.main(["shadow", *files])

    assert code == 0 and db.connects == 1 and db.commits == 1
    assert len(SLOT) == 4 and len(db.inserts) == 4 * 3  # piyasa, Elo, DC
    assert {params[0] for params in db.inserts} == {live.match_id for live in LIVE}


# Σ 1/o ≈ 0,889 < 1: karar anı fiyatını hiçbir vig yöntemi temizlemez (16i).
REJECTED = tuple(
    replace(quote, price=3.0 if quote.outcome == LIVE[0].home else 3.6)
    if quote.match_id == LIVE[0].match_id
    else quote
    for quote in QUOTES
)


@pytest.mark.parametrize(
    ("quotes", "written", "rejected"), [(QUOTES, 12, 0), (REJECTED, 11, 1)], ids=["temiz", "red"]
)
def test_the_shadow_line_counts_a_rejected_decision_price_by_name(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    quotes: tuple[Quote, ...],
    written: int,
    rejected: int,
) -> None:
    """17g: devig'in reddettiği karar anı fiyatı piyasa satırı yazdırmaz; gölge satırı onu adıyla
    sayar ve öteki sayıları değiştirmez."""
    caplog.set_level(logging.INFO, logger="football_edge.live")
    files = _patch(monkeypatch, tmp_path, _Db(), quotes=quotes)

    assert live_cli.main(["shadow", *files]) == 0
    assert (
        f"gölge: karar 4 · yazılan satır {written} · eşlenemeyen 0 · bayat durum 0 · fiyatsız 0 · "
        f"reddedilen fiyat {rejected}"
    ) in caplog.messages


# Σ 1/o = 2: power temizler, Shin'in z < 0,5 aralığında kökü yoktur — yargıyı YÖNTEM verir.
SHIN_REJECTS = tuple(
    replace(quote, price=1.5) if quote.match_id == LIVE[0].match_id else quote for quote in QUOTES
)


@pytest.mark.parametrize(
    ("method", "written", "rejected"), [(POWER, 12, 0), (SHIN, 11, 1)], ids=["power", "shin"]
)
def test_the_shadow_line_judges_prices_with_the_configured_method(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    method: str,
    written: int,
    rejected: int,
) -> None:
    """17n (son inceleme M-3): gölge satırının sayısı `config.method`le ölçülür. Öteki fikstür
    POWER'dır; sabit `POWER` yazan bir mutant orada yaşıyordu — aynı fiyatı Shin reddeder."""
    caplog.set_level(logging.INFO, logger="football_edge.live")
    files = _patch(monkeypatch, tmp_path, _Db(), quotes=SHIN_REJECTS, method=method)

    assert live_cli.main(["shadow", *files]) == 0
    assert (
        f"gölge: karar 4 · yazılan satır {written} · eşlenemeyen 0 · bayat durum 0 · fiyatsız 0 · "
        f"reddedilen fiyat {rejected}"
    ) in caplog.messages


def test_shadow_stops_on_a_lock_violation_without_writing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = _Db()
    files = _patch(monkeypatch, tmp_path, db, lock_error=True)

    assert live_cli.main(["shadow", *files]) == EXIT_LOCK_VIOLATION == 9
    assert db.inserts == [] and db.commits == 0
    assert "kilit ihlali — gölge tahmin koşulmadı: E0/holdout: fark" in caplog.messages


def test_shadow_refuses_a_changed_lock_before_connecting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db()
    files = _patch(monkeypatch, tmp_path, db)
    (tmp_path / "lock.yaml").write_text("değişti\n", encoding="utf-8")

    assert live_cli.main(["shadow", *files]) == live_cli.EXIT_CONFIG_MISMATCH == 11
    assert db.connects == 0


def test_parity_exits_fifteen_on_a_shifted_kickoff_and_zero_otherwise(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    shifted = replace(LIVE[0], kickoff=LIVE[0].kickoff + timedelta(hours=1))
    clean = _patch(monkeypatch, tmp_path, _Db())

    assert live_cli.main(["parity", *clean]) == 0
    broken = _patch(monkeypatch, tmp_path, _Db(), live=(shifted,))
    assert live_cli.main(["parity", *broken]) == live_cli.EXIT_PARITY == 15


def test_parity_stops_on_a_lock_violation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    files = _patch(monkeypatch, tmp_path, _Db(), lock_error=True)

    assert live_cli.main(["parity", *files]) == EXIT_LOCK_VIOLATION
    assert "kilit ihlali — eşitlik raporu koşulmadı: E0/holdout: fark" in caplog.messages


def test_freeze_weights_stops_on_a_lock_violation_without_writing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Kilit ihlali satırı çağrı yeri başına birebir (son inceleme M-3)."""
    files = _patch(monkeypatch, tmp_path, _Db(), lock_error=True)
    out = tmp_path / "weights.yaml"
    frozen = [*files[:6], "--out", str(out)]  # `--aliases` bu komutta yok

    assert live_cli.main(["freeze-weights", *frozen]) == EXIT_LOCK_VIOLATION
    assert not out.exists()
    assert "kilit ihlali — ağırlık dondurulmadı: E0/holdout: fark" in caplog.messages
