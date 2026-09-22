"""Bilinen sonuçlar K1–K4 (+ K2, D1 rapor): her denetim sentetik veride geçer ve kırmızı verebilir.

Veri elle kurulur: kapanış sonuca doğru kısalırsa K1 geçer, fiyatlar yer değiştirirse düşer;
Placebo'nun seçtiği tarafın fiyatı kapanışa doğru kısalırsa (gelecek fiyat sızıntısı) K4 düşer.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from functools import partial

import pytest

from football_edge.backtest import selftest
from football_edge.backtest.selftest import Check, run_selftest
from football_edge.backtest.strategies import Placebo
from football_edge.backtest.timeline import LONDON
from football_edge.history.holdout import DEV, HoldoutKey
from football_edge.history.types import CLOSING, PRE_CLOSING, RESULTS, HistMatch, OddsKey
from football_edge.market.devig import METHODS, MULTIPLICATIVE, devig
from tests.backtest_builders import hist_match, quote

RESAMPLES = 500
MAIN_LEAGUES = (
    "B1", "D1", "D2", "E0", "E1", "E2", "E3", "EC", "F1", "F2", "G1",
    "I1", "I2", "N1", "P1", "SC0", "SC1", "SC2", "SC3", "SP1", "SP2", "T1",
)  # fmt: skip
MAIN_CODES = frozenset(MAIN_LEAGUES)
Prices = tuple[float, float, float]
PRE: Prices = (2.6, 3.3, 2.8)
# Kapanış sonuca doğru kısalır (bilgi kapanışa kadar geldi) — ve keskin kitapta daha çok.
TOWARD: Mapping[str, Prices] = {"H": (1.9, 3.6, 4.2), "D": (3.2, 2.6, 3.2), "A": (4.2, 3.6, 1.9)}
SHARPER: Mapping[str, Prices] = {"H": (1.6, 4.3, 6.0), "D": (3.6, 2.1, 3.6), "A": (6.0, 4.3, 1.6)}
SLIGHT: Mapping[str, Prices] = {
    "H": (2.5, 3.3, 2.9),
    "D": (2.65, 3.2, 2.85),
    "A": (2.7, 3.3, 2.7),
}
WRONG = {"H": "A", "D": "H", "A": "D"}
SCORES = {"H": (1, 0), "D": (1, 1), "A": (0, 1)}
FAVOURITE_CLOSE: Prices = (1.5, 4.2, 6.5)
DRIFT: tuple[Prices, ...] = ((2.55, 3.3, 2.85), (2.4, 3.4, 3.0), (2.2, 3.5, 3.3), (1.9, 3.7, 4.0))
DRIFT_HOURS = {8: 0, 12: 1, 27: 1, 36: 2, 52: 2, 60: 3, 80: 3}  # karar→başlama saati: kova
PLACEBO_SEED = Placebo(devig=partial(devig, method=MULTIPLICATIVE)).seed


def _results(count: int) -> tuple[str, ...]:
    return tuple(RESULTS[index % 3] for index in range(count))


def _saturdays(count: int, first: date) -> tuple[datetime, ...]:
    """Ardışık cumartesiler 14:00 UTC: kararı cuma 12:00 Londra olan hafta sonu maçları."""
    return tuple(
        datetime.combine(first + timedelta(weeks=week), time(14), tzinfo=UTC)
        for week in range(count)
    )


def _match(
    league: str,
    kickoff: datetime,
    result: str,
    *,
    pre: Prices | None = None,
    close: Prices | None = None,
    sharp: Prices | None = None,
    season: str = "2324",
    line: int = 1,
) -> HistMatch:
    odds: dict[OddsKey, float] = {}
    if pre is not None:
        odds |= quote("Avg", PRE_CLOSING, pre)
    if close is not None:
        odds |= quote("Avg", CLOSING, close)
    if sharp is not None:
        odds |= quote("PS", CLOSING, sharp)
    return hist_match(
        day=kickoff.astimezone(LONDON).date(),
        kickoff=kickoff,
        league=league,
        season=season,
        home=f"{league} ev",
        away=f"{league} konuk",
        goals=SCORES[result],
        odds=odds,
        line=line,
    )


def _run(history: Mapping[str, Sequence[HistMatch]]) -> dict[str, Check]:
    checks = run_selftest(
        history, method=MULTIPLICATIVE, main_codes=MAIN_CODES, resamples=RESAMPLES
    )
    return {check.id: check for check in checks}


def _k1_league(
    code: str,
    *,
    swapped: bool = False,
    count: int = 6,
    first: date = date(2023, 8, 5),
    close_to: Mapping[str, Prices] = TOWARD,
) -> tuple[HistMatch, ...]:
    """Kapanış sonuca doğru kısalır; `swapped` iken kapanış öncesiyle yer değiştirir."""
    return tuple(
        _match(
            code,
            kickoff,
            result,
            pre=close_to[result] if swapped else PRE,
            close=PRE if swapped else close_to[result],
            line=index + 1,
        )
        for index, (kickoff, result) in enumerate(
            zip(_saturdays(count, first), _results(count), strict=True)
        )
    )


def _k1_history(good: int = len(MAIN_LEAGUES)) -> dict[str, tuple[HistMatch, ...]]:
    return {
        code: _k1_league(code, swapped=index >= good) for index, code in enumerate(MAIN_LEAGUES)
    }


def test_k1_passes_when_the_closing_beats_the_pre_closing_price_in_every_main_league() -> None:
    k1 = _run(_k1_history())["K1"]

    assert (k1.gate, k1.passed) == (True, True)
    assert "n=132" in k1.detail and "22/22" in k1.detail
    assert "\n" not in k1.detail


def test_k1_fails_when_the_pre_closing_and_closing_prices_are_swapped() -> None:
    k1 = _run(_k1_history(good=0))["K1"]

    assert (k1.gate, k1.passed) == (True, False)
    assert "0/22" in k1.detail


@pytest.mark.parametrize(("good", "passed"), [(18, True), (17, False)], ids=["18", "17"])
def test_k1_needs_eighteen_main_leagues_with_a_positive_gap(good: int, passed: bool) -> None:
    k1 = _run(_k1_history(good=good))["K1"]

    assert k1.passed is passed
    assert f"{good}/22" in k1.detail


def test_k1_fails_when_the_pooled_gap_is_not_above_zero_despite_eighteen_positive_leagues() -> None:
    history = {code: _k1_league(code, close_to=SLIGHT) for code in MAIN_LEAGUES[:18]}
    history |= {code: _k1_league(code, swapped=True, count=30) for code in MAIN_LEAGUES[18:]}

    k1 = _run(history)["K1"]

    assert "18/22" in k1.detail
    assert k1.passed is False


def test_k1_counts_every_main_league_of_the_catalog_even_without_data() -> None:
    k1 = _run({code: _k1_league(code) for code in MAIN_LEAGUES[:18]})["K1"]

    assert k1.passed is True
    assert "18/22" in k1.detail


def test_an_empty_history_turns_every_gate_check_red_without_crashing() -> None:
    checks = run_selftest({}, method=MULTIPLICATIVE, main_codes=MAIN_CODES, resamples=RESAMPLES)

    assert [(check.id, check.gate) for check in checks] == [
        ("K1", True),
        ("K2", False),
        ("K3", True),
        ("K4", True),
        ("D1", False),
    ]
    assert all(not check.passed and "ölçülemedi" in check.detail for check in checks)


@pytest.mark.leakage
def test_selftest_asks_select_periods_for_the_development_period_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[frozenset[str], HoldoutKey | None]] = []
    real = selftest.select_periods

    def spy(
        matches: Sequence[HistMatch], *, periods: frozenset[str], key: HoldoutKey | None = None
    ) -> tuple[HistMatch, ...]:
        asked.append((periods, key))
        return real(matches, periods=periods, key=key)

    monkeypatch.setattr(selftest, "select_periods", spy)

    _run(_k1_history())

    assert asked == [(frozenset({DEV}), None)] * len(MAIN_LEAGUES)


@pytest.mark.leakage
def test_holdout_and_later_rows_cannot_move_any_check() -> None:
    clean = _k1_history()
    later = {
        code: matches
        + _k1_league(code, swapped=True, count=12, first=date(2025, 8, 2))
        + _k1_league(code, swapped=True, count=6, first=date(2026, 8, 1))
        for code, matches in clean.items()
    }

    assert _run(later) == _run(clean)


@pytest.mark.leakage
def test_main_leagues_are_measured_only_inside_the_main_window() -> None:
    clean = _k1_history()
    early = {
        code: _k1_league(code, swapped=True, count=12, first=date(2018, 8, 4)) + matches
        for code, matches in clean.items()
    }

    assert _run(early) == _run(clean)


def _k2_history(results: str) -> dict[str, tuple[HistMatch, ...]]:
    """Ek lig (pencere EXTRA_WINDOW); kapanış belirgin bir favori gösterir."""
    kickoffs = _saturdays(len(results), date(2023, 4, 15))
    return {
        "BRA": tuple(
            _match("BRA", kickoff, result, close=FAVOURITE_CLOSE, season="2023", line=index + 1)
            for index, (kickoff, result) in enumerate(zip(kickoffs, results, strict=True))
        )
    }


def test_k2_prefers_shin_or_power_when_favourites_win_more_than_multiplicative_implies() -> None:
    k2 = _run(_k2_history("HHHHHHHHDA"))["K2"]

    assert (k2.gate, k2.passed) == (False, True)
    assert "n=10" in k2.detail
    assert all(method in k2.detail for method in METHODS)


def test_k2_is_reported_not_gated_when_multiplicative_wins() -> None:
    k2 = _run(_k2_history("HHDDDAAAAA"))["K2"]

    assert (k2.gate, k2.passed) == (False, False)


def _k3_rows(
    code: str,
    season: str,
    first: date,
    *,
    count: int = 10,
    with_sharp: int = 10,
    swapped: bool = False,
    sharp_to: Mapping[str, str] | None = None,
) -> tuple[HistMatch, ...]:
    """AvgC sonuca doğru, PSC daha keskin kısalır (`swapped`: tersi). İlk `with_sharp` satırda PSC
    var; `sharp_to` PSC'yi yanlış sonuca yöneltir."""
    rows = []
    for index, (kickoff, result) in enumerate(
        zip(_saturdays(count, first), _results(count), strict=True)
    ):
        average, sharp = TOWARD[result], SHARPER[result if sharp_to is None else sharp_to[result]]
        if swapped:
            average, sharp = sharp, average
        rows.append(
            _match(
                code,
                kickoff,
                result,
                close=average,
                sharp=sharp if index < with_sharp else None,
                season=season,
                line=index + 1,
            )
        )
    return tuple(rows)


def test_k3_passes_when_the_sharp_closing_beats_the_average_closing() -> None:
    history = {
        "E0": _k3_rows("E0", "2324", date(2023, 8, 5)),
        "BRA": _k3_rows("BRA", "2023", date(2023, 4, 15)),
    }

    k3 = _run(history)["K3"]

    assert (k3.gate, k3.passed) == (True, True)
    assert "lig-sezon 2/2" in k3.detail and "n=20" in k3.detail


def test_k3_fails_when_the_average_closing_is_sharper_than_the_sharp_book() -> None:
    k3 = _run({"E0": _k3_rows("E0", "2324", date(2023, 8, 5), swapped=True)})["K3"]

    assert (k3.gate, k3.passed) == (True, False)


@pytest.mark.parametrize(
    ("with_sharp", "passed"), [(9, False), (8, True)], ids=["ninety-kept", "eighty-dropped"]
)
def test_k3_keeps_only_league_seasons_where_both_closings_cover_ninety_percent(
    with_sharp: int, passed: bool
) -> None:
    history = {
        "E0": _k3_rows("E0", "2223", date(2022, 8, 6), with_sharp=with_sharp, sharp_to=WRONG)
        + _k3_rows("E0", "2324", date(2023, 8, 5))
    }

    k3 = _run(history)["K3"]

    assert k3.passed is passed
    assert f"lig-sezon {1 if passed else 2}/2" in k3.detail


@pytest.mark.leakage
def test_k3_measures_main_leagues_only_inside_the_main_window() -> None:
    history = {
        "E0": _k3_rows("E0", "1819", date(2018, 8, 4), count=30, swapped=True)
        + _k3_rows("E0", "2324", date(2023, 8, 5))
    }

    k3 = _run(history)["K3"]

    assert k3.passed is True
    assert "lig-sezon 1/1" in k3.detail


def _placebo_pick(index: int) -> str:
    """Placebo'nun havuzdaki `index`. maç için seçeceği sonuç (Task 4: maç başına tohum)."""
    return random.Random(PLACEBO_SEED * 1_000_003 + index).choice(RESULTS)


def _close_for(pick: str, target: float) -> Prices:
    """Çarpımsal vig temizliğinde `pick`in adil kapanış olasılığı (1 + target) / o_pre olur."""
    fair = (1.0 + target) / PRE[RESULTS.index(pick)]
    rest = (1.0 - fair) / 2
    home, draw, away = (1.0 / ((fair if name == pick else rest) * 1.05) for name in RESULTS)
    return home, draw, away


def _k4_history(
    close_of: Callable[[int, str], Prices | None], count: int = 30
) -> dict[str, tuple[HistMatch, ...]]:
    """Tek ana lig: havuzdaki sıra = listedeki sıra, `close_of(sıra, Placebo'nun seçimi)`."""
    kickoffs = _saturdays(count, date(2023, 8, 5))
    return {
        "E0": tuple(
            _match(
                "E0",
                kickoff,
                result,
                pre=PRE,
                close=close_of(index, _placebo_pick(index)),
                line=index + 1,
            )
            for index, (kickoff, result) in enumerate(zip(kickoffs, _results(count), strict=True))
        )
    }


@pytest.mark.leakage
def test_k4_passes_when_the_placebo_bets_into_prices_that_never_move() -> None:
    k4 = _run(_k4_history(lambda index, pick: PRE))["K4"]

    assert (k4.gate, k4.passed) == (True, True)
    assert "bahis=30" in k4.detail and "kapanışı eksik 0" in k4.detail


@pytest.mark.leakage
def test_k4_fails_when_the_placebo_always_picks_the_side_whose_price_shortened() -> None:
    k4 = _run(_k4_history(lambda index, pick: TOWARD[pick]))["K4"]

    assert (k4.gate, k4.passed) == (True, False)


@pytest.mark.leakage
def test_k4_fails_when_the_clv_interval_reaches_zero_despite_a_negative_mean() -> None:
    history = _k4_history(lambda index, pick: _close_for(pick, 0.2 if index % 2 == 0 else -0.25))

    k4 = _run(history)["K4"]

    found = re.search(r"CLV \(AvgC kapanışına karşı\) (\S+) \[%95 (\S+), (\S+)\]", k4.detail)
    assert found is not None, k4.detail
    estimate, _, high = (float(number) for number in found.groups())
    assert estimate < 0 < high, k4.detail
    assert k4.passed is False


def test_k4_leaves_bets_without_a_complete_closing_out_and_counts_them() -> None:
    k4 = _run(_k4_history(lambda index, pick: None if index < 3 else PRE))["K4"]

    assert k4.passed is True
    assert "bahis=27" in k4.detail and "kapanışı eksik 3" in k4.detail


def test_k4_is_red_when_the_placebo_cannot_bet() -> None:
    kickoffs = _saturdays(6, date(2023, 8, 5))
    k4 = _run({"E0": tuple(_match("E0", kickoff, "H", close=PRE) for kickoff in kickoffs)})["K4"]

    assert k4.passed is False
    assert "ölçülemedi" in k4.detail


def _d1_history(drift: Sequence[Prices], league: str = "E0") -> dict[str, tuple[HistMatch, ...]]:
    """Beş hafta; her hafta cuma 12:00 BST kararından 8–80 saat sonra başlayan yedi maç."""
    friday = datetime(2023, 8, 4, 11, tzinfo=UTC)
    slots = [(week, hours) for week in range(5) for hours in DRIFT_HOURS]
    return {
        league: tuple(
            _match(
                league,
                friday + timedelta(weeks=week, hours=hours),
                result,
                pre=PRE,
                close=drift[DRIFT_HOURS[hours]],
                line=index + 1,
            )
            for index, ((week, hours), result) in enumerate(
                zip(slots, _results(len(slots)), strict=True)
            )
        )
    }


@pytest.mark.leakage
def test_d1_passes_when_price_drift_grows_with_the_time_from_decision_to_kickoff() -> None:
    d1 = _run(_d1_history(DRIFT))["D1"]

    assert (d1.gate, d1.passed) == (False, True)
    assert re.search(r"\[0,12\) sa [0-9.]+ \(n=5\)", d1.detail), d1.detail
    for label in ("12,36", "36,60", "60,96"):
        assert re.search(rf"\[{label}\) sa [0-9.]+ \(n=10\)", d1.detail), d1.detail


@pytest.mark.leakage
def test_d1_fails_when_price_drift_shrinks_with_the_time_to_kickoff() -> None:
    d1 = _run(_d1_history(tuple(reversed(DRIFT))))["D1"]

    assert (d1.gate, d1.passed) == (False, False)


def test_k4_and_d1_measure_only_the_main_leagues() -> None:
    """Kapanış öncesi `Avg` fiyatı taşıyan bir EK lig K4'ün havuzuna ve D1'in kovalarına girmez."""
    main = _d1_history(DRIFT)
    extra = _d1_history(tuple(reversed(DRIFT)), league="BRA")

    clean, mixed = _run(main), _run({**main, **extra})

    assert "bahis=35" in mixed["K4"].detail
    assert (mixed["K4"], mixed["D1"]) == (clean["K4"], clean["D1"])
