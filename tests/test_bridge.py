"""Tarihsel ↔ canlı köprü: mühürlü kapanışın okunması, eşleme ve karşılaştırma (tasarım §9)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.history.types import CLOSING, H2H, HistMatch
from football_edge.market.bridge import (
    LiveClosing,
    Pairing,
    compare,
    load_aliases,
    load_live_closings,
    pair,
    render_bridge_report,
)
from football_edge.market.devig import MULTIPLICATIVE, SHIN, devig
from tests.fake_db import utc
from tests.market_factory import hist_match

REPO = Path(__file__).resolve().parent.parent
SINCE = datetime(2026, 7, 1, tzinfo=UTC)
HOME, AWAY = "Alpha Rovers", "Beta Athletic"
CODES = MappingProxyType({"eng.1": "E0"})
NO_ALIASES: MappingProxyType[str, str] = MappingProxyType({})


@dataclass
class _FakeClosingDb:
    """`load_live_closings`in tek sorgusu; psycopg'nin tiplerini (datetime, Decimal) verir."""

    rows: list[tuple[Any, ...]]
    executed: list[tuple[str, Any]] = field(default_factory=list)

    def cursor(self) -> _Cursor:
        return _Cursor(self)


class _Cursor:
    def __init__(self, db: _FakeClosingDb) -> None:
        self._db = db

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        self._db.executed = [*self._db.executed, (" ".join(sql.split()), params)]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._db.rows)


def _row(
    match_id: str,
    book: str,
    outcome: str,
    price: float,
    *,
    observed: str = "2026-09-19T13:50:00Z",
    kickoff: str = "2026-09-19T14:00:00Z",
) -> tuple[Any, ...]:
    return (
        match_id,
        "eng.1",
        utc(kickoff),
        HOME,
        AWAY,
        book,
        outcome,
        Decimal(str(price)),
        utc(observed),
    )


def _book(match_id: str, book: str, prices: tuple[float, float, float]) -> list[tuple[Any, ...]]:
    names = (HOME, "Draw", AWAY)
    return [_row(match_id, book, name, price) for name, price in zip(names, prices, strict=True)]


def test_consensus_is_the_mean_over_books_that_carry_all_three_outcomes() -> None:
    rows = [
        *_book("m1", "book_a", (2.0, 3.4, 4.0)),
        *_book("m1", "book_b", (2.2, 3.6, 3.8)),
        _row("m1", "book_c", HOME, 2.1),  # beraberliği yok: ortalamaya girmez
        _row("m1", "book_c", AWAY, 3.9),
    ]
    (closing,) = load_live_closings(_FakeClosingDb(rows), since=SINCE)  # type: ignore[arg-type]
    assert closing.prices == pytest.approx((2.1, 3.5, 3.9))
    assert closing.books == 2
    assert all(type(price) is float for price in closing.prices)
    assert (closing.match_id, closing.league_id, closing.home, closing.away) == (
        "m1",
        "eng.1",
        HOME,
        AWAY,
    )
    assert closing.kickoff == datetime(2026, 9, 19, 14, 0, tzinfo=UTC)


def test_outcomes_are_mapped_by_team_name_not_by_row_order() -> None:
    rows = [
        _row("m1", "book_a", AWAY, 5.0),
        _row("m1", "book_a", "Draw", 3.8),
        _row("m1", "book_a", HOME, 1.7),
    ]
    (closing,) = load_live_closings(_FakeClosingDb(rows), since=SINCE)  # type: ignore[arg-type]
    assert closing.prices == (1.7, 3.8, 5.0)


def test_the_latest_closing_snapshot_of_a_book_wins() -> None:
    # Pencere iki mühür turunu kapsayabilir: başlamaya en yakın gözlem kapanıştır.
    rows = [
        _row("m1", "book_a", HOME, 2.0, observed="2026-09-19T13:55:00Z"),
        _row("m1", "book_a", HOME, 2.5, observed="2026-09-19T13:40:00Z"),
        _row("m1", "book_a", "Draw", 3.4),
        _row("m1", "book_a", AWAY, 4.0),
    ]
    (closing,) = load_live_closings(_FakeClosingDb(rows), since=SINCE)  # type: ignore[arg-type]
    assert closing.prices == (2.0, 3.4, 4.0)


def test_query_reads_only_h2h_closing_rows_of_matches_since_the_given_time() -> None:
    db = _FakeClosingDb([])
    assert load_live_closings(db, since=SINCE) == ()  # type: ignore[arg-type]
    ((sql, params),) = db.executed
    assert "JOIN odds_snapshots s ON s.match_id = m.id" in sql
    assert "s.is_closing" in sql
    assert "s.market = %s" in sql
    assert "m.commence_time >= %s" in sql
    assert params == ("h2h", SINCE)


def test_a_match_without_a_complete_book_is_skipped_and_named(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rows = [*_book("m1", "book_a", (2.0, 3.4, 4.0)), _row("m2", "book_a", HOME, 2.0)]
    with caplog.at_level(logging.WARNING, logger="football_edge.market.bridge"):
        closings = load_live_closings(_FakeClosingDb(rows), since=SINCE)  # type: ignore[arg-type]
    assert [closing.match_id for closing in closings] == ["m1"]
    assert "maç=m2" in caplog.text


def test_closings_come_back_in_kickoff_order() -> None:
    late = [
        _row("m9", "book_a", name, price, kickoff="2026-09-20T18:00:00Z")
        for name, price in zip((HOME, "Draw", AWAY), (2.0, 3.4, 4.0), strict=True)
    ]
    rows = [*late, *_book("m1", "book_a", (2.0, 3.4, 4.0))]
    closings = load_live_closings(_FakeClosingDb(rows), since=SINCE)  # type: ignore[arg-type]
    assert [closing.match_id for closing in closings] == ["m1", "m9"]


def _live(
    match_id: str = "m1",
    *,
    league_id: str = "eng.1",
    kickoff: datetime = datetime(2026, 9, 19, 14, 0, tzinfo=UTC),
    home: str = HOME,
    away: str = AWAY,
    prices: tuple[float, float, float] = (2.0, 4.0, 4.0),
) -> LiveClosing:
    return LiveClosing(match_id, league_id, kickoff, home, away, prices, 2)


def _hist(
    day: date,
    *,
    league: str = "E0",
    home: str = HOME,
    away: str = AWAY,
    avgc: tuple[float, float, float] | None = (2.0, 4.0, 4.0),
) -> HistMatch:
    prices = {} if avgc is None else {("Avg", H2H, CLOSING): avgc}
    return hist_match(league=league, season="2627", day=day, home=home, away=away, prices=prices)


def test_pairs_on_league_code_date_and_team_names() -> None:
    live = _live()
    target = _hist(date(2026, 9, 19))
    result = pair([live], [target], aliases=NO_ALIASES, codes_by_league_id=CODES)
    assert result == Pairing(pairs=((live, target),), unmatched_live=())


@pytest.mark.parametrize(
    ("kickoff", "london_day"),
    (
        (datetime(2026, 9, 19, 23, 30, tzinfo=UTC), date(2026, 9, 20)),  # BST: 00:30 ertesi gün
        (datetime(2026, 11, 7, 23, 30, tzinfo=UTC), date(2026, 11, 7)),  # GMT: 23:30 aynı gün
    ),
)
def test_pairing_uses_the_london_date_of_the_kickoff(kickoff: datetime, london_day: date) -> None:
    hist = [_hist(london_day + timedelta(days=shift)) for shift in (-1, 0, 1)]
    result = pair([_live(kickoff=kickoff)], hist, aliases=NO_ALIASES, codes_by_league_id=CODES)
    ((_, found),) = result.pairs
    assert found.date == london_day


@pytest.mark.parametrize("side", ("home", "away"))
def test_alias_maps_the_odds_api_name_to_the_football_data_name(side: str) -> None:
    # Takma ad ev ve deplasman adına AYRI AYRI uygulanır (m4: yalnız ev sınanıyordu).
    live = _live(**{side: "Delta Rovers United"})
    hist = [_hist(date(2026, 9, 19), **{side: "Delta Rov."})]
    aliases = MappingProxyType({"Delta Rovers United": "Delta Rov"})
    assert pair([live], hist, aliases=aliases, codes_by_league_id=CODES).pairs
    unaliased = pair([live], hist, aliases=NO_ALIASES, codes_by_league_id=CODES)
    assert unaliased.unmatched_live == (live,)


def test_names_are_compared_after_normalisation() -> None:
    live = _live(away="Beta Athletic F.C.")
    hist = [_hist(date(2026, 9, 19), away="BETA ATHLETIC")]
    assert pair([live], hist, aliases=NO_ALIASES, codes_by_league_id=CODES).pairs


def test_unmatched_live_matches_are_returned_in_order_not_dropped() -> None:
    unknown_league = _live("m1", league_id="xyz.9")
    no_counterpart = _live("m2", home="Gamma United")
    paired = _live("m3")
    hist = [_hist(date(2026, 9, 19)), _hist(date(2026, 9, 19), league="SP1", home="Gamma United")]
    result = pair(
        [unknown_league, no_counterpart, paired], hist, aliases=NO_ALIASES, codes_by_league_id=CODES
    )
    assert result.unmatched_live == (unknown_league, no_counterpart)
    assert [live.match_id for live, _ in result.pairs] == ["m3"]


@pytest.mark.leakage
def test_the_bridge_never_pairs_a_holdout_dated_match() -> None:
    # Holdout [2025-07-01, 2026-07-01) anahtarsız okunmaz: köprü yalnız "sonrası"na bakar.
    live = _live(kickoff=datetime(2026, 3, 14, 15, 0, tzinfo=UTC))
    hist = [_hist(date(2026, 3, 14), avgc=(2.0, 4.0, 4.0))]
    result = pair([live], hist, aliases=NO_ALIASES, codes_by_league_id=CODES)
    assert result.pairs == ()
    assert result.unmatched_live == (live,)


def test_compare_reports_ours_minus_avgc_per_outcome_and_the_rms() -> None:
    # Çift 1: bizim (2, 4, 4) → (0.5, 0.25, 0.25); AvgC (2.5, 10/3, 10/3) → (0.4, 0.3, 0.3)
    #   fark (0.1, −0.05, −0.05). Çift 2: iki taraf aynı → fark 0.
    #   ortalama (0.05, −0.025, −0.025) · RMS = √((0.01 + 0.0025 + 0.0025) / 6) = 0.05
    first = (_live("m1"), _hist(date(2026, 9, 19), avgc=(2.5, 10 / 3, 10 / 3)))
    second = (_live("m2", home="Gamma United"), _hist(date(2026, 9, 19), home="Gamma United"))
    pairing = Pairing(pairs=(first, second), unmatched_live=(_live("m3"),))
    report = compare(pairing, method=MULTIPLICATIVE)
    assert (report.n, report.method, report.unmatched) == (2, MULTIPLICATIVE, 1)
    estimates = tuple(interval.estimate for interval in report.mean_diff)
    assert estimates == pytest.approx((0.05, -0.025, -0.025), abs=1e-12)
    assert report.rms == pytest.approx(0.05, abs=1e-12)
    home = report.mean_diff[0]
    assert home.low <= home.estimate <= home.high


def test_compare_devigs_both_sides_with_the_same_method() -> None:
    ours, theirs = (1.8, 3.6, 4.6), (1.9, 3.5, 4.2)
    pairing = Pairing(
        pairs=((_live(prices=ours), _hist(date(2026, 9, 19), avgc=theirs)),), unmatched_live=()
    )
    report = compare(pairing, method=SHIN)
    expected = tuple(a - b for a, b in zip(devig(ours, SHIN), devig(theirs, SHIN), strict=True))
    estimates = tuple(interval.estimate for interval in report.mean_diff)
    assert estimates == pytest.approx(expected, abs=1e-12)


def test_pairs_without_a_closing_avgc_are_counted_as_unmatched() -> None:
    usable = (_live("m1"), _hist(date(2026, 9, 19)))
    bare = (
        _live("m2", home="Gamma United"),
        _hist(date(2026, 9, 19), home="Gamma United", avgc=None),
    )
    report = compare(Pairing(pairs=(usable, bare), unmatched_live=()), method=SHIN)
    assert (report.n, report.unmatched) == (1, 1)


def test_compare_without_comparable_pairs_is_an_error() -> None:
    with pytest.raises(ValueError, match="karşılaştırılabilir"):
        compare(Pairing(pairs=(), unmatched_live=(_live(),)), method=SHIN)


def test_bridge_report_carries_only_aggregates() -> None:
    first = (_live("m1"), _hist(date(2026, 9, 19), avgc=(2.5, 10 / 3, 10 / 3)))
    second = (_live("m2", home="Gamma United"), _hist(date(2026, 9, 19), home="Gamma United"))
    pairing = Pairing(pairs=(first, second), unmatched_live=(_live("m3"),))
    report = compare(pairing, method=MULTIPLICATIVE)
    generated = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
    text = render_bridge_report(report, generated_at=generated, since=date(2026, 7, 1))
    assert "Karşılaştırılan maç (N): 2" in text
    assert "Karşılaştırılamayan canlı maç: 1" in text
    assert "Yöntem: multiplicative" in text
    assert "2026-07-01 ve sonrasında" in text
    home = report.mean_diff[0]
    assert f"| H | +0.0500 | [{home.low:+.4f}, {home.high:+.4f}] |" in text
    assert "| D | -0.0250 |" in text
    assert "| A | -0.0250 |" in text
    assert "RMS (bütün sonuç farkları): 0.0500" in text
    assert "Aralık N küçükken geniştir (N = 2)" in text
    for name in (HOME, AWAY, "Gamma United"):
        assert name not in text  # takım adı (ham satır) rapora giremez
    assert text.endswith("\n")


def test_load_aliases_reads_an_immutable_string_mapping(tmp_path: Path) -> None:
    path = tmp_path / "aliases.yaml"
    path.write_text("aliases:\n  Alpha Rovers United: Alpha Rov\n", encoding="utf-8")
    aliases = load_aliases(path)
    assert dict(aliases) == {"Alpha Rovers United": "Alpha Rov"}
    with pytest.raises(TypeError):
        aliases["x"] = "y"  # type: ignore[index]


@pytest.mark.parametrize(
    "text",
    ("", "aliases: [a, b]\n", "other: {}\n", "aliases:\n  Alpha: 3\n", "aliases:\n  Alpha: ''\n"),
    ids=("bos", "liste", "anahtar-yok", "sayi", "bos-hedef"),
)
def test_load_aliases_rejects_a_malformed_file(tmp_path: Path, text: str) -> None:
    path = tmp_path / "aliases.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="aliases|takma ad"):
        load_aliases(path)


def test_repository_alias_file_loads() -> None:
    aliases = load_aliases(REPO / "config/history_aliases.yaml")
    assert all(isinstance(key, str) and isinstance(value, str) for key, value in aliases.items())
