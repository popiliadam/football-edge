"""Haftalık gölge CLV raporu (Faz 4 tasarımı §2 T0a, §5/5; DEFERRED 16o, 16e). Veritabanı yok:
okuyucular kayıt tutan sahte bağlantıyla, rapor elle kurulmuş satırlarla sınanır."""

from __future__ import annotations

import ast
import inspect
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from football_edge.backtest.model_config import MODEL_CONFIG_PATH, file_sha256, load_model_config
from football_edge.backtest.walkforward import BLEND_COMPONENTS, DC, ELO, MARKET
from football_edge.backtest.wf_eval import MARKET_ONLY, bet_clv
from football_edge.live import __main__ as live_cli
from football_edge.live import report as report_module
from football_edge.live import store as store_module
from football_edge.live.report import build_report, render_report
from football_edge.live.store import (
    BASE_STRATEGIES,
    PredictionRow,
    load_closing,
    load_outcomes,
    load_predictions,
)
from football_edge.live.weights import BlendWeights, dump_blend_weights, freeze
from football_edge.market.devig import POWER, devig
from football_edge.market.metrics import per_match_log_loss
from football_edge.model.pool import pool

SHA = "e" * 64
SINCE = datetime(2026, 9, 1, tzinfo=UTC)
DECIDED = datetime(2026, 10, 2, 11, tzinfo=UTC)
JEV = "harman_" + "jev"  # Faz 4 T6'nın stratejisi; raporun hiçbir yolu onu okumamalı
WEIGHTS = BlendWeights(
    "a" * 64, "b" * 64, "c" * 64, BLEND_COMPONENTS, MARKET_ONLY, {"E0": (0.5, 0.3, 0.2)}, ("E1",)
)


class _Cursor:
    def __init__(self, conn: _Conn) -> None:
        self.conn = conn

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.conn.log.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self.conn.rows)


class _Conn:
    def __init__(self, rows: Sequence[tuple[Any, ...]] = ()) -> None:
        self.rows = rows
        self.log: list[tuple[str, tuple[Any, ...]]] = []

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def __enter__(self) -> _Conn:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _stored(match_id: str, strategy: str, league: str = "E0") -> tuple[Any, ...]:
    """psycopg'nin döndürdüğü biçim: olasılık `double precision`, fiyat `numeric` → Decimal."""
    return (
        match_id,
        f"{league}|2026-10-03|Alfa|Beta",
        strategy,
        0.5,
        0.3,
        0.2,
        Decimal("2.10"),
        Decimal("3.40"),
        Decimal("3.60"),
        DECIDED,
        SHA,
    )


def test_predictions_are_parsed_with_the_league_code_from_the_match_key() -> None:
    conn = _Conn([_stored("m1", MARKET, league="SP1")])

    (row,) = load_predictions(
        conn,  # type: ignore[arg-type]
        since=SINCE,
        strategies=BASE_STRATEGIES,
        model_config_sha256=SHA,
    )

    assert row == PredictionRow(
        "m1",
        "SP1|2026-10-03|Alfa|Beta",
        "SP1",
        MARKET,
        (0.5, 0.3, 0.2),
        (2.1, 3.4, 3.6),
        DECIDED,
        SHA,
    )
    assert all(isinstance(value, float) for value in row.pre)


@pytest.mark.leakage
def test_the_prediction_query_asks_only_for_the_base_strategies() -> None:
    conn = _Conn()

    load_predictions(
        conn,  # type: ignore[arg-type]
        since=SINCE,
        strategies=BASE_STRATEGIES,
        model_config_sha256=SHA,
    )

    ((sql, params),) = conn.log
    assert "strategy = ANY(%s)" in sql and "model_config_sha256 = %s" in sql
    assert params == (SINCE, SHA, sorted(BASE_STRATEGIES)) == (SINCE, SHA, [DC, ELO, MARKET])


@pytest.mark.leakage
@pytest.mark.parametrize(
    "strategies",
    [frozenset({JEV}), BASE_STRATEGIES | {JEV}, frozenset()],
    ids=["jev", "mix", "boş"],
)
def test_a_non_base_strategy_is_refused_before_any_query(strategies: frozenset[str]) -> None:
    conn = _Conn()

    with pytest.raises(ValueError, match="mühür"):
        load_predictions(
            conn,  # type: ignore[arg-type]
            since=SINCE,
            strategies=strategies,
            model_config_sha256=SHA,
        )
    assert conn.log == []


@pytest.mark.leakage
def test_a_stray_strategy_returned_by_the_query_breaks_the_seal() -> None:
    conn = _Conn([_stored("m1", MARKET), _stored("m1", JEV)])

    with pytest.raises(ValueError, match="mühür"):
        load_predictions(
            conn,  # type: ignore[arg-type]
            since=SINCE,
            strategies=BASE_STRATEGIES,
            model_config_sha256=SHA,
        )


def _strings(module: object) -> list[str]:
    tree = ast.parse(inspect.getsource(module))  # type: ignore[arg-type]
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


@pytest.mark.leakage
def test_every_query_on_the_prediction_table_filters_by_strategy() -> None:
    """Mühür kaynakta: tabloyu okuyan her SQL metni strateji süzgecini taşır; rapor modülü SQL
    taşımaz, veritabanı modülü import etmez ve Jev stratejisinin adını hiç anmaz."""
    queries = [text for text in _strings(store_module) if "model_predictions" in text]
    imported = {
        alias.name if isinstance(node, ast.Import) else node.module or ""
        for node in ast.walk(ast.parse(inspect.getsource(report_module)))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert queries and all("strategy = ANY(%s)" in text for text in queries)
    assert not any("SELECT" in text.upper() for text in _strings(report_module))
    assert not imported & {"psycopg", "football_edge.db"}
    for module in (report_module, store_module):
        assert JEV not in inspect.getsource(module)


@pytest.mark.leakage
def test_the_report_refuses_a_non_base_row() -> None:
    row = PredictionRow("m1", "E0|x|a|b", "E0", JEV, (0.5, 0.3, 0.2), (2.0, 3.0, 4.0), DECIDED, SHA)

    with pytest.raises(ValueError, match="mühür"):
        build_report([row], {}, {}, WEIGHTS, tau=0.02, method=POWER, resamples=20)


CLOSING_ROUND = datetime(2026, 10, 3, 13, 40, tzinfo=UTC)


def _closing_row(
    match_id: str, at: datetime, book: str, outcome: str, price: str
) -> tuple[Any, ...]:
    return (match_id, at, book, outcome, Decimal(price), "Alfa", "Beta")


def test_the_closing_is_the_full_book_average_of_the_latest_round() -> None:
    earlier = CLOSING_ROUND - timedelta(minutes=10)
    conn = _Conn(
        [
            *(_closing_row("m1", earlier, "b1", name, "9.0") for name in ("Alfa", "Draw", "Beta")),
            _closing_row("m1", CLOSING_ROUND, "b1", "Alfa", "2.0"),
            _closing_row("m1", CLOSING_ROUND, "b1", "Draw", "3.0"),
            _closing_row("m1", CLOSING_ROUND, "b1", "Beta", "4.0"),
            _closing_row("m1", CLOSING_ROUND, "b2", "Alfa", "2.2"),
            _closing_row("m1", CLOSING_ROUND, "b2", "Draw", "3.2"),
            _closing_row("m1", CLOSING_ROUND, "b2", "Beta", "4.4"),
            _closing_row("m1", CLOSING_ROUND, "b3", "Alfa", "5.0"),  # eksik kitap: sayılmaz
            _closing_row("m2", CLOSING_ROUND, "b1", "Alfa", "2.0"),
        ]
    )

    found = load_closing(conn, ("m1", "m2"))  # type: ignore[arg-type]

    ((sql, params),) = conn.log
    assert "o.is_closing" in sql and params == (["m1", "m2"], "h2h")
    assert set(found) == {"m1"}
    assert found["m1"] == pytest.approx((2.1, 3.1, 4.2))


def test_the_newest_completed_result_wins() -> None:
    first, correction = DECIDED + timedelta(days=1), DECIDED + timedelta(days=2)
    conn = _Conn(
        [
            # Sorgunun sırası (`ORDER BY match_id, observed_at`, eski → yeni): ilk gözlemi tutan
            # okuyucu 2-0'ı, en yeniyi tutan düzeltmeyi (1-1) döndürür.
            ("m1", first, 2, 0),
            ("m1", correction, 1, 1),
            ("m2", first, 0, 3),
            ("m3", first, 2, 1),
        ]
    )

    found = load_outcomes(conn, ("m1", "m2", "m3"))  # type: ignore[arg-type]

    ((sql, params),) = conn.log
    assert "AND completed" in sql and params == (["m1", "m2", "m3"],)
    assert dict(found) == {"m1": 1, "m2": 2, "m3": 0}


def test_no_match_ids_means_no_query() -> None:
    conn = _Conn()

    assert dict(load_closing(conn, ())) == {}  # type: ignore[arg-type]
    assert dict(load_outcomes(conn, ())) == {}  # type: ignore[arg-type]
    assert conn.log == []


def _predictions(
    match_id: str,
    league: str,
    pre: tuple[float, float, float],
    names: Sequence[str] = (MARKET, ELO, DC),
) -> list[PredictionRow]:
    probs = {MARKET: (0.5, 0.3, 0.2), ELO: (0.7, 0.2, 0.1), DC: (0.6, 0.25, 0.15)}
    return [
        PredictionRow(
            match_id, f"{league}|2026-10-03|A|B", league, name, probs[name], pre, DECIDED, SHA
        )
        for name in names
    ]


def test_the_report_blends_with_the_frozen_weights_and_counts_every_loss() -> None:
    predictions = [
        *_predictions("m1", "E0", (2.4, 3.4, 3.6)),  # tam, sonuçlu, kapanışlı → bahis
        *_predictions("m2", "E1", (2.0, 3.4, 4.2)),  # tam, sonuçlu, kapanışsız; havuz ağırlığı
        *_predictions("m3", "E0", (2.0, 3.4, 4.2), (MARKET, ELO)),  # DC yok: eksik
        *_predictions("m4", "E0", (2.0, 3.4, 4.2)),  # kapanışı çözülemez (fiyat 1.0)
    ]
    closing = {"m1": (2.0, 3.5, 4.0), "m4": (1.0, 3.5, 4.0)}
    outcomes = {"m1": 0, "m2": 2, "m3": 0}
    fixtures = {"m1": "E0", "m2": "E1", "m3": "E0", "x9": "SP1"}

    report = build_report(
        predictions,
        closing,
        outcomes,
        WEIGHTS,
        tau=0.02,
        method=POWER,
        resamples=50,
        fixtures=fixtures,
    )

    m1 = pool([(0.5, 0.3, 0.2), (0.7, 0.2, 0.1), (0.6, 0.25, 0.15)], (0.5, 0.3, 0.2))
    m2 = (0.5, 0.3, 0.2)  # E1 havuza düşer: havuz yalnız piyasa
    blend_ll = per_match_log_loss([m1, m2], [0, 2])
    market_ll = per_match_log_loss([(0.5, 0.3, 0.2)] * 2, [0, 2])
    expected_clv = bet_clv(m1, (2.4, 3.4, 3.6), devig((2.0, 3.5, 4.0), POWER), 0.02)
    assert expected_clv is not None
    assert (report.decided, report.incomplete, report.settled, report.closed) == (4, 1, 2, 1)
    assert report.bad_closing == 1
    assert report.blend_log_loss is not None and report.blend_gap is not None
    assert report.blend_log_loss.estimate == pytest.approx(sum(blend_ll) / 2)
    assert report.blend_gap.estimate == pytest.approx(
        sum(b - m for b, m in zip(blend_ll, market_ll, strict=True)) / 2
    )
    assert report.bets == 1 and report.bet_clv is not None
    assert report.bet_clv.estimate == pytest.approx(expected_clv)
    assert report.fallback == ("E1",)
    assert {league: tuple(vars(c).values()) for league, c in report.leagues.items()} == {
        "E0": (2, 2, 1, 1, 1),
        "E1": (1, 1, 1, 1, 0),
        "SP1": (1, 0, 0, 0, 0),
    }


def test_an_empty_series_renders_as_unmeasured_not_as_zero() -> None:
    report = build_report((), {}, {}, WEIGHTS, tau=0.02, method=POWER, resamples=20)

    text = render_report(report, generated_at=DECIDED)

    assert report.blend_log_loss is None and report.bet_clv is None and report.bets == 0
    assert text.count("ölçülemedi") == 4
    assert "Karar verilen maç 0" in text


def test_the_rendered_report_carries_totals_but_no_match_row() -> None:
    predictions = [*_predictions("m1", "E0", (2.4, 3.4, 3.6))]
    report = build_report(
        predictions,
        {"m1": (2.0, 3.5, 4.0)},
        {"m1": 0},
        WEIGHTS,
        tau=0.02,
        method=POWER,
        resamples=20,
        fixtures={"m1": "E0"},
    )

    text = render_report(report, generated_at=DECIDED)

    assert "m1" not in text and JEV not in text
    assert f"`{WEIGHTS.model_config_sha256}`" in text
    assert "| E0 | 1 | 1 | 1 | 1 | 1 |" in text
    assert "bahis 1" in text


def _real_weights(tmp_path: Path, **change: str) -> Path:
    config = load_model_config(MODEL_CONFIG_PATH)
    digests = {
        "model_config_sha256": file_sha256(MODEL_CONFIG_PATH),
        "lock_sha256": config.lock_sha256,
        "catalog_sha256": config.catalog_sha256,
        **change,
    }
    path = tmp_path / "weights.yaml"
    path.write_text(dump_blend_weights(freeze((), ["E0"], **digests)), encoding="utf-8")
    return path


def test_the_report_command_reads_only_the_base_series_of_the_frozen_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def predictions(conn: object, **kwargs: Any) -> tuple[PredictionRow, ...]:
        seen.update(kwargs)
        return tuple(_predictions("m1", "E0", (2.4, 3.4, 3.6)))

    monkeypatch.setattr(live_cli, "connect", _Conn)
    monkeypatch.setattr(live_cli, "load_predictions", predictions)
    monkeypatch.setattr(live_cli, "load_closing", lambda conn, ids: {"m1": (2.0, 3.5, 4.0)})
    monkeypatch.setattr(live_cli, "load_outcomes", lambda conn, ids: {"m1": 0})
    monkeypatch.setattr(live_cli, "load_live_matches", lambda conn, **kwargs: ())
    out = tmp_path / "rapor.md"

    code = live_cli.main(
        [
            "report",
            "--weights",
            str(_real_weights(tmp_path)),
            "--out",
            str(out),
            "--resamples",
            "20",
        ]
    )

    assert code == 0
    assert seen == {
        "since": live_cli.REPORT_SINCE,
        "strategies": BASE_STRATEGIES,
        "model_config_sha256": file_sha256(MODEL_CONFIG_PATH),
    }
    assert "Karar verilen maç 1" in out.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "change",
    [{"model_config_sha256": "0" * 64}, {"lock_sha256": "0" * 64}, {"catalog_sha256": "0" * 64}],
)
def test_the_report_refuses_weights_frozen_for_another_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, str]
) -> None:
    monkeypatch.setattr(live_cli, "connect", _Conn)
    out = tmp_path / "rapor.md"

    code = live_cli.main(
        ["report", "--weights", str(_real_weights(tmp_path, **change)), "--out", str(out)]
    )

    assert code == live_cli.EXIT_CONFIG_MISMATCH
    assert not out.exists()


def test_the_report_refuses_a_missing_weights_file(tmp_path: Path) -> None:
    out = tmp_path / "rapor.md"

    code = live_cli.main(["report", "--weights", str(tmp_path / "yok.yaml"), "--out", str(out)])

    assert code == live_cli.EXIT_CONFIG_MISMATCH
    assert not out.exists()


def test_a_partial_latest_closing_round_does_not_fall_back_to_an_earlier_one() -> None:
    """Review Focus: son kapanış turunda tam kitap yoksa önceki tura düşülmez (karar fiyatıyla
    aynı kural, 16e); maç kapanışsız sayılır ve kapsam tablosunda görünür, sessizce değil."""
    earlier = CLOSING_ROUND - timedelta(minutes=10)
    conn = _Conn(
        [
            *(_closing_row("m1", earlier, "b1", name, "2.5") for name in ("Alfa", "Draw", "Beta")),
            _closing_row("m1", CLOSING_ROUND, "b1", "Alfa", "2.0"),
            _closing_row("m1", CLOSING_ROUND, "b1", "Draw", "3.0"),
        ]
    )

    closing = load_closing(conn, ("m1",))  # type: ignore[arg-type]
    report = build_report(
        _predictions("m1", "E0", (2.4, 3.4, 3.6)),
        closing,
        {"m1": 0},
        WEIGHTS,
        tau=0.02,
        method=POWER,
        resamples=20,
        fixtures={"m1": "E0"},
    )

    assert dict(closing) == {}
    assert (report.closed, report.bad_closing, report.bets) == (0, 0, 0)
    assert report.leagues["E0"].closed == 0 and report.leagues["E0"].settled == 1


def test_a_since_with_an_offset_is_converted_not_relabelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review Focus: `--since 2026-09-01T03:00+03:00` UTC gece yarısıdır; dilimi silmek (`parity`nin
    `replace(tzinfo=UTC)` kalıbı) pencereyi üç saat kaydırırdı."""
    seen: dict[str, Any] = {}

    def predictions(conn: object, **kwargs: Any) -> tuple[PredictionRow, ...]:
        seen.update(kwargs)
        return ()

    monkeypatch.setattr(live_cli, "connect", _Conn)
    monkeypatch.setattr(live_cli, "load_predictions", predictions)
    monkeypatch.setattr(live_cli, "load_closing", lambda conn, ids: {})
    monkeypatch.setattr(live_cli, "load_outcomes", lambda conn, ids: {})
    monkeypatch.setattr(live_cli, "load_live_matches", lambda conn, **kwargs: ())
    weights, out = _real_weights(tmp_path), tmp_path / "rapor.md"

    for text in ("2026-09-01T03:00:00+03:00", "2026-09-01"):
        assert (
            live_cli.main(["report", "--weights", str(weights), "--out", str(out), "--since", text])
            == 0
        )
        assert seen["since"] == datetime(2026, 9, 1, tzinfo=UTC)
