"""Walk-forward satırları ve değerlendirmesi (Faz 3 tasarımı §5, §6.3–6.5). Veri SENTETİK."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from types import MappingProxyType

import pytest

from football_edge.backtest import wf_eval
from football_edge.backtest.records import MatchKey
from football_edge.backtest.walkforward import (
    DC,
    DC_TOTALS,
    ELO,
    EVALUATION,
    MARKET,
    SELECTION,
    Row,
    group_kind,
    group_matches,
    group_rows,
    zone_of,
)
from football_edge.backtest.wf_eval import (
    BLEND,
    MARKET_ONLY,
    bet_clv,
    fold_weights,
    summarise,
)
from football_edge.history.catalog import EXTRA, MAIN
from football_edge.history.types import TOTALS_25
from football_edge.market.devig import POWER
from football_edge.market.metrics import per_match_log_loss
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModel
from football_edge.model.pool import MIN_FIT_MATCHES, NotConverged
from football_edge.model.strategies import DixonColesStrategy
from tests.backtest_builders import hist_match
from tests.model_builders import main_history

KINDS = MappingProxyType({"E0": MAIN, "E1": MAIN, "BRA": EXTRA})


def _strategies() -> dict[str, object]:
    dc = DixonColesStrategy(config=DCConfig(min_matches=40), active_from=date(2012, 7, 1))
    return {
        ELO: EloModel(),
        DC: dc,
        DC_TOTALS: DixonColesStrategy(
            config=dc.config, active_from=dc.active_from, market=TOTALS_25, memo=dc.memo
        ),
    }


@pytest.mark.parametrize(
    ("day", "kind", "zone"),
    [
        (date(2012, 6, 30), MAIN, None),
        (date(2012, 7, 1), MAIN, SELECTION),
        (date(2019, 6, 30), MAIN, SELECTION),
        (date(2019, 7, 1), MAIN, EVALUATION),
        (date(2025, 6, 30), MAIN, EVALUATION),
        (date(2025, 7, 1), MAIN, None),
        (date(2012, 12, 31), EXTRA, None),
        (date(2013, 1, 1), EXTRA, SELECTION),
        (date(2018, 7, 1), EXTRA, EVALUATION),
        (date(2026, 8, 1), EXTRA, None),
    ],
)
@pytest.mark.leakage
def test_zones_stay_inside_the_development_period(day: date, kind: str, zone: str | None) -> None:
    assert zone_of(hist_match(day=day), kind) == zone


def test_groups_join_the_leagues_of_a_country_in_a_fixed_order() -> None:
    late = hist_match(day=date(2020, 1, 4), league="E1", home="Gama", away="Delta")
    early = hist_match(day=date(2020, 1, 3), league="E0")
    other = hist_match(day=date(2020, 1, 2), league="BRA")

    grouped = group_matches(
        {"E1": (late,), "E0": (early,), "BRA": (other,)},
        {"E0": "England", "E1": "England", "BRA": "Brazil"},
    )

    assert list(grouped) == ["Brazil", "England"]
    assert grouped["England"] == (early, late)


def test_a_group_mixing_main_and_extra_leagues_is_refused() -> None:
    with pytest.raises(ValueError, match="ana ve ek"):
        group_kind(
            (hist_match(day=date(2020, 1, 4)), hist_match(day=date(2020, 1, 4), league="BRA")),
            KINDS,
        )


@pytest.fixture(scope="module")
def rows() -> tuple[Row, ...]:
    return group_rows(main_history(2011, 2021), KINDS, _strategies(), method=POWER)  # type: ignore[arg-type]


def test_rows_come_only_from_the_selection_and_evaluation_zones(rows: tuple[Row, ...]) -> None:
    assert {row.zone for row in rows} == {SELECTION, EVALUATION}
    assert min(row.key.date for row in rows) >= date(2012, 7, 1)


def test_the_market_component_reads_bbav_in_selection_and_avg_in_evaluation(
    rows: tuple[Row, ...],
) -> None:
    selection = [row for row in rows if row.zone == SELECTION]
    evaluation = [row for row in rows if row.zone == EVALUATION]

    assert all(MARKET in row.components and row.closing is None for row in selection)
    assert all(MARKET in row.components and row.closing is not None for row in evaluation)
    assert all(row.pre is not None for row in rows)
    assert all(
        MARKET in row.totals and DC in row.totals for row in evaluation if row.components.get(DC)
    )


def test_model_components_are_present_once_the_models_have_history(rows: tuple[Row, ...]) -> None:
    late = [row for row in rows if row.key.date >= date(2014, 1, 1)]

    assert all(ELO in row.components for row in late)
    assert sum(DC in row.components for row in late) == len(late)


def _row(league: str, season: str, zone: str, outcome: int, index: int) -> Row:
    market, elo, dc = (0.5, 0.3, 0.2), (0.2, 0.3, 0.5), (0.34, 0.33, 0.33)
    return Row(
        key=MatchKey(league, date(2020, 1, 1), f"Ev {index}", f"Konuk {index}"),
        kind=MAIN,
        zone=zone,
        season=season,
        outcome=outcome,
        totals_outcome=0,
        components=MappingProxyType({MARKET: market, ELO: elo, DC: dc}),
        totals=MappingProxyType({}),
        pre=(2.0, 3.2, 4.5),
        closing=(0.48, 0.3, 0.22),
        totals_pre=None,
        totals_closing=None,
    )


def _table(outcome_of: dict[str, int], count: int = MIN_FIT_MATCHES) -> list[Row]:
    """Sezon → her maçta hep aynı sonuç: 0 piyasayı, 2 Elo'yu haklı çıkarır."""
    zones = {"1819": SELECTION, "1920": EVALUATION, "2021": EVALUATION, "2122": EVALUATION}
    return [
        _row("E0", season, zones[season], outcome, index + 1000 * position)
        for position, (season, outcome) in enumerate(outcome_of.items())
        for index in range(count)
    ]


@pytest.mark.leakage
def test_a_seasons_weights_never_see_that_season_or_later() -> None:
    """G3: `s`'nin satırları değişince `s`'nin ağırlığı değişmez, `s`'den sonrakininki değişir."""
    base = _table({"1819": 0, "1920": 0, "2021": 0, "2122": 0})
    flipped = _table({"1819": 0, "1920": 0, "2021": 2, "2122": 0})

    before, _ = fold_weights(base)
    after, _ = fold_weights(flipped)

    assert after[("E0", "1920")] == before[("E0", "1920")]
    assert after[("E0", "2021")] == before[("E0", "2021")]
    assert after[("E0", "2122")] != before[("E0", "2122")]


def test_the_first_evaluation_season_uses_the_selection_rows() -> None:
    weights, _ = fold_weights(_table({"1819": 2, "1920": 0}))

    market, elo, _dc = weights[("E0", "1920")]
    assert elo > market


def test_a_thin_league_falls_back_to_the_pooled_rows_and_then_to_the_market() -> None:
    thin = _table({"1819": 0, "1920": 0}, count=10)

    weights, fallback = fold_weights(thin)

    assert weights[("E0", "1920")] == MARKET_ONLY
    assert fallback == ("E0/1920",)


def test_a_league_below_the_league_minimum_takes_the_pooled_weights() -> None:
    """Tek ligin ~bir sezonu (< LEAGUE_MIN_MATCHES) kendi ağırlığını fit etmez: gürültüsü W1'i
    aşardı."""
    small = _table({"1819": 0, "1920": 0}, count=wf_eval.LEAGUE_MIN_MATCHES - 1)

    _, fallback = fold_weights(small)

    assert fallback == ("E0/1920",)


@pytest.mark.parametrize(
    ("probs", "tau", "expected"),
    [
        ((0.6, 0.25, 0.15), 0.02, 2.0 * 0.48 - 1.0),  # H: 0.6·2.0 − 1 = 0.2 en büyük, > τ
        ((0.5, 0.3, 0.2), 0.02, None),  # en büyük EV 0.0 ≤ τ
        ((0.45, 0.2, 0.35), 0.5, 4.5 * 0.22 - 1.0),  # A: 0.35·4.5 − 1 = 0.575 > 0.5
        ((0.45, 0.2, 0.35), 0.6, None),  # 0.575 ≤ 0.6
    ],
)
def test_the_bet_rule_takes_the_largest_edge_above_tau(
    probs: tuple[float, float, float], tau: float, expected: float | None
) -> None:
    found = bet_clv(probs, (2.0, 3.2, 4.5), (0.48, 0.3, 0.22), tau)

    if expected is None:
        assert found is None
    else:
        assert found == pytest.approx(expected)


def test_no_bet_without_a_pre_price_or_a_closing() -> None:
    assert bet_clv((0.9, 0.05, 0.05), None, (0.4, 0.3, 0.3), 0.0) is None
    assert bet_clv((0.9, 0.05, 0.05), (2.0, 3.0, 4.0), None, 0.0) is None


def test_the_summary_compares_on_common_rows_and_is_deterministic(rows: tuple[Row, ...]) -> None:
    """G7: aynı satırlar → aynı özet."""
    first = summarise(rows, tau=0.02, sensitivity=(0.0, 0.05), resamples=50)
    second = summarise(rows, tau=0.02, sensitivity=(0.0, 0.05), resamples=50)

    assert first == second
    assert set(first.main) == {MARKET, ELO, DC, BLEND}
    assert len({score.n for score in first.main.values()}) == 1
    assert first.blend_gap is not None and set(first.league_gaps) == {"E0"}
    assert set(first.clv_sensitivity) == {0.0, 0.05}
    assert set(first.totals) == {MARKET, DC}


def test_rows_missing_a_component_are_counted_not_blended(rows: tuple[Row, ...]) -> None:
    evaluation = [row for row in rows if row.zone == EVALUATION]
    broken = replace(evaluation[0], components=MappingProxyType({MARKET: (0.5, 0.3, 0.2)}))

    summary = summarise((*rows, broken), tau=0.02, sensitivity=(), resamples=20)

    assert wf_eval.complete(broken) is False
    assert summary.incomplete == 1
    assert summary.main[BLEND].n == len(evaluation)


@pytest.mark.leakage
def test_frozen_weights_never_see_holdout_or_post_rows() -> None:
    """I2: `final_eval`in satırları holdout ve sonrası bölgelerini TAM bileşenle taşır; ağırlık
    yalnız geliştirmenin E'sinden gelir: holdout satırları Elo'yu haklı çıkarsa da ağırlık aynı."""
    development = _table({"1819": 0, "1920": 0}, count=wf_eval.LEAGUE_MIN_MATCHES)
    holdout = [
        replace(
            _row("E0", "2526", zone, 2, index),
            key=MatchKey("E0", date(2026, 1, 1), f"H{index}", "K"),
        )
        for zone in ("holdout", "post")
        for index in range(3000)
    ]

    alone, _ = wf_eval.frozen_weights(development, [("E0", "2526")])
    mixed, _ = wf_eval.frozen_weights([*development, *holdout], [("E0", "2526")])

    assert mixed == alone


def _never_converges(*args: object, **kwargs: object) -> tuple[float, ...]:
    raise NotConverged("ağırlık fiti yakınsamadı: test")


def test_a_fit_that_does_not_converge_falls_back_to_the_market_and_is_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """16a: yakınsamama açılıştan sonra exit 14 değil, adıyla sayılan bir geri düşüştür."""
    monkeypatch.setattr(wf_eval, "fit_weights", _never_converges)
    table = _table({"1819": 0, "1920": 0}, count=wf_eval.LEAGUE_MIN_MATCHES)

    folded, folded_fallback = fold_weights(table)
    frozen, frozen_fallback = wf_eval.frozen_weights(table, [("E0", "2526")])

    assert folded[("E0", "1920")] == frozen[("E0", "2526")] == MARKET_ONLY
    assert folded_fallback == ("E0/1920",) and frozen_fallback == ("E0/2526",)


def test_a_programming_error_in_the_fit_is_not_a_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """16a: yalnız az maç ve yakınsamama geri düşüştür; düz `ValueError` (programlama hatası)
    yükselir — sessizce MARKET_ONLY'e sayılmaz."""

    def broken(*args: object, **kwargs: object) -> tuple[float, ...]:
        raise ValueError("3 bileşen, 2 sonuç")

    monkeypatch.setattr(wf_eval, "fit_weights", broken)
    table = _table({"1819": 0, "1920": 0}, count=wf_eval.LEAGUE_MIN_MATCHES)
    with pytest.raises(ValueError, match="sonuç"):
        fold_weights(table)
    with pytest.raises(ValueError, match="sonuç"):
        wf_eval.frozen_weights(table, [("E0", "2526")])


def _mean_gap(
    first: list[tuple[float, ...]], second: list[tuple[float, ...]], outcomes: list[int]
) -> float:
    a, b = per_match_log_loss(first, outcomes), per_match_log_loss(second, outcomes)
    return sum(x - y for x, y in zip(a, b, strict=True)) / len(outcomes)


def test_each_component_and_the_totals_are_paired_against_the_market(
    rows: tuple[Row, ...],
) -> None:
    """16c: C2 ve C5 strateji başına LL değil, piyasaya karşı AYNI satırlarda ΔLL'dir."""
    summary = summarise(rows, tau=0.02, sensitivity=(), resamples=50)
    common = [row for row in rows if row.zone == EVALUATION and wf_eval.complete(row)]
    outcomes = [row.outcome for row in common]
    market = [row.components[MARKET] for row in common]
    totals = [
        row for row in rows if row.zone == EVALUATION and MARKET in row.totals and DC in row.totals
    ]

    assert set(summary.component_gaps) == {ELO, DC}
    for name, gap in summary.component_gaps.items():
        own = [row.components[name] for row in common]
        assert gap.estimate == pytest.approx(_mean_gap(own, market, outcomes))
    assert summary.totals_gap is not None
    assert summary.totals_gap.estimate == pytest.approx(
        _mean_gap(
            [row.totals[DC] for row in totals],
            [row.totals[MARKET] for row in totals],
            [row.totals_outcome for row in totals],
        )
    )
