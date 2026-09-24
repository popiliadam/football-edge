"""Tur konsensüsü tek tanım (Faz 6 İz B §4.3): yaprak modül; `pre_prices` ve site onu çağırır."""

from __future__ import annotations

import ast
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, OddsKey
from football_edge.live import context
from football_edge.live.context import LiveMatch, pre_prices
from football_edge.market.consensus import LIVE_DRAW, LIVE_H2H, Quote, round_consensus

SRC = Path(__file__).resolve().parent.parent / "src" / "football_edge"
T0 = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
MATCH = LiveMatch("m1", "tst.1", T1 + timedelta(hours=5), "Ev", "Dep")


def _book(book: str, at: datetime, prices: tuple[float, float, float]) -> list[Quote]:
    return [
        Quote("m1", at, book, LIVE_H2H, name, price)
        for name, price in zip(("Ev", LIVE_DRAW, "Dep"), prices, strict=True)
    ]


QUOTES = [
    *_book("a", T0, (2.0, 3.0, 4.0)),
    *_book("b", T0, (2.2, 3.2, 3.8)),
    *_book("a", T1, (2.1, 3.1, 3.9)),
    *_book("b", T1, (2.3, 3.3, 3.7)),
    Quote("m1", T1, "c", LIVE_H2H, "Ev", 9.0),  # eksik kitap: ev ve beraberlik var, deplasman yok
    Quote("m1", T1, "c", LIVE_H2H, LIVE_DRAW, 9.0),
    Quote("m1", T1, "a", "totals", "Over", 1.9),  # başka market
]


def test_the_round_mean_uses_only_full_books_of_that_round() -> None:
    found = round_consensus(QUOTES, T1, "Ev", "Dep")

    assert found is not None
    assert found.books == 2
    assert found.means == pytest.approx((2.2, 3.2, 3.8))


def test_a_round_without_a_full_book_has_no_consensus() -> None:
    assert round_consensus([Quote("m1", T0, "a", LIVE_H2H, "Ev", 2.0)], T0, "Ev", "Dep") is None
    assert round_consensus(QUOTES, T1 + timedelta(minutes=1), "Ev", "Dep") is None


def test_pre_prices_is_the_latest_round_consensus_under_the_reference_key() -> None:
    """Davranış eşitliği: `pre_prices` = karar anından önceki SON turun `round_consensus`u."""
    found = pre_prices(QUOTES, MATCH, T1)
    expected = round_consensus(QUOTES, T1, "Ev", "Dep")

    assert found is not None and expected is not None
    assert [found[OddsKey(context.REFERENCE_BOOK, H2H, o, PRE_CLOSING)] for o in RESULTS] == list(
        expected.means
    )
    assert pre_prices(QUOTES, MATCH, T0 - timedelta(seconds=1)) is None


def test_the_round_mean_is_the_exact_fsum_float_in_both_callers() -> None:
    """Mühürlü kapanış (`load_closing` → `pre_prices`) bu float'ı taşır: toplama biçimi sabittir.

    Ev fiyatları 1.1, 1.2, 3.4 (bu sırayla üç tam kitap): `math.fsum` → 1.9000000000000001,
    Python 3.11'in düz `sum`ı → 1.8999999999999997 (T2 M3; CI 3.11 koşar). `approx` değil `==`.
    Önkoşul: iki toplama bu yorumlayıcıda AYRIŞIR — 3.12+'nın `sum`ı telafili toplar ve ikisi
    eşitlenir; o zaman pin `sum`a dönüşü artık yakalamaz ve test bunu adıyla söyler (B-1 son
    düzeltme yeniden incelemesi (b)).
    """
    home = [1.1, 1.2, 3.4]
    assert sum(home) / 3 != math.fsum(home) / 3, (
        "önkoşul düştü: bu Python'da sum ile math.fsum aynı float'ı veriyor (3.12+ telafili "
        "toplar); pin yalnız Python 3.11'de (CI) ayırt edicidir — ayrışan başka bir fiyat üçlüsü "
        "seçilmeli"
    )
    quotes = [
        *_book("a", T0, (1.1, 5.0, 9.0)),
        *_book("b", T0, (1.2, 5.0, 9.0)),
        *_book("c", T0, (3.4, 5.0, 9.0)),
    ]

    found = round_consensus(quotes, T0, "Ev", "Dep")
    prices = pre_prices(quotes, MATCH, T0)

    assert found is not None and prices is not None
    assert found.means[0] == 1.9000000000000001
    assert (
        prices[OddsKey(context.REFERENCE_BOOK, H2H, RESULTS[0], PRE_CLOSING)] == 1.9000000000000001
    )


def test_a_later_round_of_another_market_does_not_move_pre_prices() -> None:
    """`pre_prices` en son turu yalnız 1X2 satırları arasında seçer: sonraki bir `totals` turu
    kararı None'a düşürmez ve fiyatı değiştirmez."""
    later_totals = Quote("m1", T1 + timedelta(minutes=5), "a", "totals", "Over", 1.9)

    with_totals = pre_prices([*QUOTES, later_totals], MATCH, T1 + timedelta(minutes=10))

    assert with_totals is not None
    assert with_totals == pre_prices(QUOTES, MATCH, T1)


def test_live_context_re_exports_the_moved_names() -> None:
    """`live/store.py` ve testler importlarını değiştirmez."""
    assert context.Quote is Quote
    assert (context.LIVE_H2H, context.LIVE_DRAW) == (LIVE_H2H, LIVE_DRAW)


def test_the_consensus_module_is_a_leaf_that_imports_only_history_types() -> None:
    tree = ast.parse((SRC / "market" / "consensus.py").read_text(encoding="utf-8"))
    internal = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("football_edge")
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.startswith("football_edge")
    }

    assert internal == {"football_edge.history.types"}
