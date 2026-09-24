"""Tur konsensüsü tek tanım (Faz 6 İz B §4.3): yaprak modül; `pre_prices` ve site onu çağırır."""

from __future__ import annotations

import ast
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
