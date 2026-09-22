"""Piyasa verimliliği: ölçüt tanımları, dönem ayrımı, sıralama, adaylar, rapor (tasarım §8)."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, date, datetime
from types import MappingProxyType

import numpy as np
import pytest

from football_edge.history.catalog import EXTRA, MAIN, HistoryLeague
from football_edge.history.holdout import DEV, DEV_END, HOLDOUT, HOLDOUT_END
from football_edge.history.lock import Digest, HistoryLock
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, HistMatch
from football_edge.market import efficiency
from football_edge.market.devig import METHODS, MULTIPLICATIVE, SHIN, match_probs, overround
from football_edge.market.efficiency import (
    LeagueEfficiency,
    NoClosingPrices,
    Ranking,
    Unmeasurable,
    best_method,
    candidates,
    league_efficiency,
    method_scores,
    rank,
    render_report,
)
from football_edge.market.metrics import (
    Calibration,
    Interval,
    brier,
    calibration,
    log_loss,
    outcome_index,
    per_match_log_loss,
    rps,
)
from tests.efficiency_samples import (
    BASE,
    CLOSE_SETS,
    EXTRA_LEAGUE,
    FAIR_HOMES,
    MAIN_LEAGUE,
    TOTAL_SETS,
    added,
    calibrated,
    rich,
    synthetic,
)
from tests.market_factory import with_prices

FAST = 40  # testlerde bootstrap tekrarı; üretim varsayılanı 2000


def _closing_probs(
    matches: tuple[HistMatch, ...], method: str, book: str = "Avg"
) -> list[tuple[float, ...] | None]:
    return [match_probs(m, book=book, market=H2H, phase=CLOSING, method=method) for m in matches]


def _results(matches: tuple[HistMatch, ...]) -> list[int]:
    return [outcome_index(match, H2H) for match in matches]


def test_n_counts_only_matches_with_a_complete_closing_1x2() -> None:
    bare = tuple(replace(match, odds=MappingProxyType({})) for match in synthetic(4, first=100))
    result = league_efficiency(MAIN_LEAGUE, (*BASE, *bare), method=SHIN, resamples=FAST)
    assert (result.code, result.league_id, result.kind, result.n) == ("M1", "m.1", MAIN, 56)


def test_margin_and_closing_accuracy_use_avgc_devigged_with_the_method() -> None:
    result = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=FAST)
    probs, outcomes = _closing_probs(BASE, SHIN), _results(BASE)
    margins = [overround(CLOSE_SETS[index % 4]) for index in range(56)]
    assert result.margin.estimate == pytest.approx(math.fsum(margins) / 56)
    assert result.log_loss.estimate == pytest.approx(log_loss(probs, outcomes))
    assert result.brier == pytest.approx(brier(probs, outcomes))
    assert result.rps == pytest.approx(rps(probs, outcomes))
    assert result.calibration == calibration(probs, outcomes)
    plain = league_efficiency(MAIN_LEAGUE, BASE, method=MULTIPLICATIVE, resamples=FAST)
    assert plain.log_loss.estimate != pytest.approx(result.log_loss.estimate)


def test_slope_interval_refits_the_calibration_on_resampled_matches() -> None:
    result = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=FAST)
    assert result.slope.estimate == result.calibration.slope
    assert result.slope.low < result.slope.estimate < result.slope.high
    fewer = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=10)
    assert (fewer.slope.low, fewer.slope.high) != (result.slope.low, result.slope.high)


def test_late_info_is_pre_closing_minus_closing_log_loss_per_match() -> None:
    # Kapanış öncesi (3, 3, 3) → (1/3, 1/3, 1/3): LL_öncesi her maçta ln 3. Yalnız ilk 40 maçta
    # kapanış öncesi fiyat var; ΔLL o 40 maçın ortalamasıdır.
    early = (*added(BASE[:40], {("Avg", H2H, PRE_CLOSING): (3.0, 3.0, 3.0)}), *BASE[40:])
    result = league_efficiency(MAIN_LEAGUE, early, method=MULTIPLICATIVE, resamples=FAST)
    closing = log_loss(_closing_probs(BASE[:40], MULTIPLICATIVE), _results(BASE[:40]))
    assert result.late_info is not None
    assert result.late_info.estimate == pytest.approx(math.log(3) - closing)


def test_extra_leagues_have_no_late_info_value_rate_or_totals() -> None:
    extra = rich(synthetic(56, league="X1", season="2023"))
    result = league_efficiency(EXTRA_LEAGUE, extra, method=SHIN, resamples=FAST)
    assert result.n == 56
    assert (result.late_info, result.value_rate) == (None, None)
    assert (result.ou25_margin, result.ou25_log_loss, result.ou25_calibration) == (None, None, None)


def test_value_rate_counts_matches_where_a_best_price_beats_the_fair_closing_probability() -> None:
    # Çarpımsal yöntemde Max_i · p_i = (Max_i / AvgC_i) / B. Değer YALNIZ ev sonucunda: i % 3 == 0
    # ise Max_H = AvgC_H × 1.2 (1.2 / B > 1), öteki sonuçlar × 1.0 (1/B ≤ 1). "Herhangi bir sonuç"
    # tanımı (tasarım §8.2) bu maçları sayar; "her sonuç" (min) hiçbirini saymazdı.
    # Adil kümede (B = 1) Max = AvgC çarpımı TAM 1'dir ve değer SAYILMAZ (> 1, ≥ değil).
    # Son altı maçta Max yok: paydaya girmezler. Değer: i < 50 ve i % 3 == 0 → 17/50.
    best = tuple(
        with_prices(
            match,
            {
                ("Max", H2H, PRE_CLOSING): tuple(
                    price * (1.2 if index % 3 == 0 and outcome == 0 else 1.0)
                    for outcome, price in enumerate(CLOSE_SETS[index % 4])
                )
            },
        )
        for index, match in enumerate(BASE[:50])
    )
    result = league_efficiency(
        MAIN_LEAGUE, (*best, *BASE[50:]), method=MULTIPLICATIVE, resamples=FAST
    )
    assert result.value_rate is not None
    assert result.value_rate.estimate == pytest.approx(17 / 50)


def test_sharp_gap_uses_only_seasons_where_avgc_and_psc_are_ninety_percent_complete() -> None:
    full = synthetic(20, start=date(2020, 8, 1), season="2021")
    edge = synthetic(20, start=date(2021, 8, 7), season="2122", first=20)  # 18/20 = %90: girer
    thin = synthetic(20, start=date(2022, 8, 6), season="2223", first=40)  # 17/20 = %85: girmez
    sharp = {("PS", H2H, CLOSING): (1.9, 3.8, 3.8)}
    seasons = (*added(full, sharp), *added(edge[:18], sharp), *edge[18:])
    matches = (*seasons, *added(thin[:17], sharp), *thin[17:])
    result = league_efficiency(MAIN_LEAGUE, matches, method=SHIN, resamples=FAST)
    used = (*added(full, sharp), *added(edge[:18], sharp))
    average = per_match_log_loss(_closing_probs(used, SHIN), _results(used))
    keen = per_match_log_loss(_closing_probs(used, SHIN, book="PS"), _results(used))
    assert result.sharp_gap is not None
    expected = math.fsum(a - s for a, s in zip(average, keen, strict=True)) / len(used)
    assert result.sharp_gap.estimate == pytest.approx(expected)


def test_sharp_and_exchange_gaps_are_none_when_no_season_qualifies() -> None:
    result = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=FAST)
    assert (result.sharp_gap, result.exchange_gap) == (None, None)


def test_exchange_gap_uses_only_seasons_where_avgc_and_bfec_are_ninety_percent_complete() -> None:
    # R97 (D3 "BFEC varsa raporlanır"): keskinlik farkıyla aynı kural, kitap BFE (Betfair borsası).
    # PSC hiç yok: iki fark birbirinden bağımsız hesaplanır.
    full = synthetic(20, start=date(2023, 8, 5), season="2324", first=600)  # 20/20: girer
    thin = synthetic(20, start=date(2024, 8, 3), season="2425", first=620)  # 17/20: girmez
    exchange = {("BFE", H2H, CLOSING): (1.8, 4.0, 4.4)}
    matches = (*added(full, exchange), *added(thin[:17], exchange), *thin[17:])
    result = league_efficiency(MAIN_LEAGUE, matches, method=SHIN, resamples=FAST)
    used = added(full, exchange)
    average = per_match_log_loss(_closing_probs(used, SHIN), _results(used))
    betfair = per_match_log_loss(_closing_probs(used, SHIN, book="BFE"), _results(used))
    assert result.sharp_gap is None
    assert result.exchange_gap is not None
    expected = math.fsum(a - b for a, b in zip(average, betfair, strict=True)) / len(used)
    assert result.exchange_gap.estimate == pytest.approx(expected)


def test_totals_metrics_use_the_closing_over_under_on_main_leagues() -> None:
    totals = tuple(
        with_prices(match, {("Avg", TOTALS_25, CLOSING): TOTAL_SETS[index % 3]})
        for index, match in enumerate(BASE)
    )
    result = league_efficiency(MAIN_LEAGUE, totals, method=SHIN, resamples=FAST)
    probs = [
        match_probs(match, book="Avg", market=TOTALS_25, phase=CLOSING, method=SHIN)
        for match in totals
    ]
    outcomes = [outcome_index(match, TOTALS_25) for match in totals]
    margins = [overround(TOTAL_SETS[index % 3]) for index in range(56)]
    assert result.ou25_margin is not None
    assert result.ou25_margin.estimate == pytest.approx(math.fsum(margins) / 56)
    assert result.ou25_log_loss is not None
    assert result.ou25_log_loss.estimate == pytest.approx(log_loss(probs, outcomes))
    assert result.ou25_calibration == calibration(probs, outcomes)
    bare = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=FAST)
    assert (bare.ou25_margin, bare.ou25_log_loss, bare.ou25_calibration) == (None, None, None)


def test_a_league_without_closing_prices_is_a_named_error() -> None:
    bare = tuple(replace(match, odds=MappingProxyType({})) for match in BASE)
    with pytest.raises(NoClosingPrices, match="M1"):
        league_efficiency(MAIN_LEAGUE, bare, method=SHIN, resamples=FAST)


def _later() -> tuple[HistMatch, ...]:
    """Holdout ve sonrası tarihli, ölçütleri belirgin biçimde değiştirecek maçlar."""
    holdout = synthetic(56, start=date(2025, 8, 2), season="2526", first=200)
    post = synthetic(16, start=date(2026, 8, 1), season="2627", first=300)
    lopsided = {("Avg", H2H, CLOSING): (1.3, 5.5, 11.0)}
    return rich(added((*holdout, *post), lopsided))


@pytest.mark.leakage
def test_holdout_and_post_matches_never_reach_any_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pencere bilerek devre dışı bırakılır (R89: holdout'a uzanan pencere kurulamaz): holdout'u
    # yalnız dönem süzgeci durdurur. Koruma: pencerenin normalde düşürdüğü 2018/19 maçı geçmeli.
    monkeypatch.setattr(efficiency, "in_window", lambda match, window: True)
    early = synthetic(4, start=date(2018, 8, 4), season="1819", first=700)
    assert efficiency._development_rows(MAIN_LEAGUE, early) == early, "yama etkisiz: test kör kalır"
    development = rich(BASE)
    mixed = league_efficiency(MAIN_LEAGUE, (*development, *_later()), method=SHIN, resamples=FAST)
    assert mixed == league_efficiency(MAIN_LEAGUE, development, method=SHIN, resamples=FAST)


@pytest.mark.leakage
def test_method_scores_ignore_matches_outside_the_development_period() -> None:
    assert method_scores((*BASE, *_later())) == method_scores(BASE)


def test_main_window_drops_development_matches_before_2019_20_but_extra_keeps_them() -> None:
    early = synthetic(20, start=date(2018, 8, 4), season="1819", first=400)
    assert league_efficiency(MAIN_LEAGUE, (*BASE, *early), method=SHIN, resamples=FAST).n == 56
    extra = synthetic(56, league="X1", season="2023")
    extra_early = synthetic(20, start=date(2014, 3, 1), league="X1", season="2014", first=500)
    result = league_efficiency(EXTRA_LEAGUE, (*extra, *extra_early), method=SHIN, resamples=FAST)
    assert result.n == 76


def test_method_scores_compare_every_method_on_the_same_matches() -> None:
    # Σ 1/o < 1: Shin çözemez → bu maç HİÇBİR yöntemin puanına girmez (ortak küme).
    under = with_prices(synthetic(1, first=900)[0], {("Avg", H2H, CLOSING): (2.2, 4.4, 4.4)})
    scores = method_scores((*BASE, under))
    assert tuple(scores) == METHODS
    for method in METHODS:
        assert scores[method] == pytest.approx(
            log_loss(_closing_probs(BASE, method), _results(BASE))
        )


def test_best_method_picks_the_lowest_log_loss_and_breaks_ties_by_name() -> None:
    assert best_method({"multiplicative": 0.99, "power": 0.97, "shin": 0.98}) == "power"
    assert best_method({"multiplicative": 0.97, "power": 0.98, "shin": 0.97}) == "multiplicative"


def _row(
    code: str,
    *,
    kind: str = MAIN,
    n: int = 1500,
    late: tuple[float, float, float] | None = None,
    slope: tuple[float, float, float] = (1.0, 0.95, 1.05),
    ece: float = 0.01,
) -> LeagueEfficiency:
    """Sıralama/aday testleri için elle kurulan satır; yalnız ilgili alanlar anlamlı."""
    return LeagueEfficiency(
        code=code,
        league_id=code.lower(),
        kind=kind,
        n=n,
        margin=Interval(0.05, 0.04, 0.06),
        log_loss=Interval(0.97, 0.96, 0.98),
        brier=0.57,
        rps=0.19,
        calibration=Calibration(slope=slope[0], intercept=0.0, ece=ece, n=3 * n),
        slope=Interval(*slope),
        late_info=None if late is None else Interval(*late),
        value_rate=None,
        sharp_gap=None,
        ou25_margin=None,
        ou25_log_loss=None,
        ou25_calibration=None,
        exchange_gap=None,
    )


def test_rank_orders_late_info_descending_over_main_leagues_only() -> None:
    rows = (
        _row("M1", late=(0.02, 0.01, 0.03)),
        _row("M2", late=(0.05, 0.04, 0.06)),
        _row("M3", late=(0.03, 0.02, 0.04)),
        _row("X1", kind=EXTRA),
    )
    assert rank(rows).late_info == ("M2", "M3", "M1")


def test_rank_orders_miscalibration_by_slope_distance_then_ece() -> None:
    rows = (
        _row("L1", kind=EXTRA, slope=(0.5, 0.45, 0.55)),  # |b − 1| = 0.5
        _row("L2", kind=EXTRA, slope=(1.25, 1.2, 1.3), ece=0.01),  # 0.25, ECE küçük
        _row("L3", kind=EXTRA, slope=(0.75, 0.7, 0.8), ece=0.03),  # 0.25, ECE büyük
        _row("L4", kind=EXTRA, slope=(1.0, 0.95, 1.05)),  # 0
    )
    assert rank(rows).miscalibration == ("L1", "L3", "L2", "L4")


def test_tiers_compare_interval_ends_with_the_median_estimate() -> None:
    # Altı ek lig kalibrasyon medyanını 0.3'e çeker: ana liglerin kalibrasyon kademesi C olur ve
    # görünen kademe yalnız geç bilgininkidir. Geç bilgi medyanı 0.02.
    main = (
        _row("M1", late=(0.05, 0.04, 0.06)),  # alt uç > medyan → A
        _row("M2", late=(0.03, 0.02, 0.04)),  # alt uç = medyan → A DEĞİL, B
        _row("M3", late=(0.02, 0.01, 0.03)),  # medyanı içerir → B
        _row("M4", late=(0.01, 0.0, 0.015)),  # üst uç < medyan → C
        _row("M5", late=(0.015, 0.005, 0.02)),  # üst uç = medyan → C DEĞİL, B
    )
    tight = tuple(replace(row, slope=Interval(1.01, 1.005, 1.015)) for row in main)
    padding = tuple(_row(f"E{i}", kind=EXTRA, slope=(1.3, 1.29, 1.31)) for i in range(6))
    tiers = rank((*tight, *padding)).tiers
    assert {code: tiers[code] for code in ("M1", "M2", "M3", "M4", "M5")} == {
        "M1": "A",
        "M2": "B",
        "M3": "B",
        "M4": "C",
        "M5": "B",
    }
    assert {tiers[f"E{i}"] for i in range(6)} == {"B"}


def test_a_league_takes_the_better_of_its_two_tiers() -> None:
    rows = (
        _row("P1", late=(0.05, 0.045, 0.055), slope=(1.0, 0.99, 1.01)),  # geç A · kalibrasyon B
        _row("P2", late=(0.03, 0.025, 0.035), slope=(1.0, 0.99, 1.01)),  # geç B · kalibrasyon B
        _row("P3", late=(0.01, 0.005, 0.015), slope=(1.5, 1.45, 1.55)),  # geç C · kalibrasyon A
    )
    assert dict(rank(rows).tiers) == {"P1": "A", "P2": "B", "P3": "A"}


def test_miscalibration_tier_uses_the_distance_interval_of_the_slope() -> None:
    # Q1 (0.5, 0.7) → |b−1| ∈ [0.3, 0.5] · Q2 (0.7, 1.45) 1'i içerir → [0, 0.45] · Q3 → [0.15, 0.25]
    # Medyan 0.2: Q1 A; Q2'nin alt ucu 0 → B (uçların mutlak değeri [0.3, 0.45] A derdi); Q3 B.
    rows = (
        _row("Q1", kind=EXTRA, slope=(0.6, 0.5, 0.7)),
        _row("Q2", kind=EXTRA, slope=(1.0, 0.7, 1.45)),
        _row("Q3", kind=EXTRA, slope=(1.2, 1.15, 1.25)),
    )
    assert dict(rank(rows).tiers) == {"Q1": "A", "Q2": "B", "Q3": "B"}


def _lock(coverage: dict[str, tuple[int, int]]) -> HistoryLock:
    """Lig → (holdout AvgC tam satır, holdout satır); holdout SATIRI yok, yalnız özet."""
    return HistoryLock(
        canonical_version=1,
        locked_at=date(2026, 9, 29),
        dev_end=DEV_END,
        holdout_end=HOLDOUT_END,
        leagues=MappingProxyType(
            {
                code: MappingProxyType(
                    {
                        DEV: Digest(rows=5000, sha256="0" * 64, avgc_complete=5000),
                        HOLDOUT: Digest(rows=rows, sha256="1" * 64, avgc_complete=complete),
                    }
                )
                for code, (complete, rows) in coverage.items()
            }
        ),
    )


def _catalog_entry(code: str, key: str) -> HistoryLeague:
    return HistoryLeague(code, code.lower(), code, "Xland", 1, MAIN, "0506", key)


def _chosen(
    *, n: int = 1000, holdout: tuple[int, int] = (95, 100), key: str = "soccer_c1", tier: str = "B"
) -> tuple[str, ...]:
    ranking = Ranking(late_info=(), miscalibration=("C1",), tiers=MappingProxyType({"C1": tier}))
    return candidates(
        (_row("C1", n=n),),
        ranking,
        lock=_lock({"C1": holdout}),
        leagues=(_catalog_entry("C1", key),),
    )


def test_a_league_at_every_boundary_is_a_candidate() -> None:
    assert _chosen() == ("C1",)  # N = 1000, holdout 95/100 = %95, anahtar var, kademe B


@pytest.mark.parametrize(
    "change",
    ({"n": 999}, {"key": ""}, {"tier": "C"}),
    ids=("n-999", "anahtar-yok", "kademe-c"),
)
def test_candidates_need_enough_matches_an_api_key_and_tier_a_or_b(
    change: dict[str, object],
) -> None:
    assert _chosen(**change) == ()  # type: ignore[arg-type]


@pytest.mark.leakage
@pytest.mark.parametrize("holdout", ((94, 100), (0, 0)), ids=("yuzde-94", "holdout-bos"))
def test_holdout_coverage_comes_from_the_lock_digest(holdout: tuple[int, int]) -> None:
    assert _chosen(holdout=holdout) == ()


def test_candidates_are_ordered_by_tier_then_code() -> None:
    ranking = Ranking(
        late_info=(), miscalibration=("C1", "C2"), tiers=MappingProxyType({"C1": "B", "C2": "A"})
    )
    chosen = candidates(
        (_row("C1"), _row("C2")),
        ranking,
        lock=_lock({"C1": (100, 100), "C2": (100, 100)}),
        leagues=(_catalog_entry("C1", "k1"), _catalog_entry("C2", "k2")),
    )
    assert chosen == ("C2", "C1")


def test_candidates_refuse_a_league_missing_from_the_lock_or_the_catalog() -> None:
    ranking = Ranking(late_info=(), miscalibration=("C1",), tiers=MappingProxyType({"C1": "A"}))
    with pytest.raises(ValueError, match="kilitte"):
        candidates((_row("C1"),), ranking, lock=_lock({}), leagues=(_catalog_entry("C1", "k"),))
    with pytest.raises(ValueError, match="kataloğunda"):
        candidates((_row("C1"),), ranking, lock=_lock({"C1": (100, 100)}), leagues=())


UNMEASURED = HistoryLeague("X9", "x.9", "Boş Lig", "Zland", 1, EXTRA, "", "")


def _report(scores: dict[str, float], chosen: tuple[str, ...] = ("M1",)) -> str:
    main = league_efficiency(MAIN_LEAGUE, rich(BASE), method=SHIN, resamples=FAST)
    extra = league_efficiency(
        EXTRA_LEAGUE, synthetic(56, league="X1", season="2023"), method=SHIN, resamples=FAST
    )
    return render_report(
        (main, extra),
        rank((main, extra)),
        scores=scores,
        candidates=chosen,
        generated_at=datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
        unmeasured=(UNMEASURED,),
    )


SHIN_BEST = {"multiplicative": 0.99, "power": 0.98, "shin": 0.97}


def test_report_has_every_section_and_only_aggregates() -> None:
    text = _report(SHIN_BEST)
    for heading in (
        "# Piyasa verimliliği — geliştirme dönemi",
        "## Vig yöntemleri (K2)",
        "## Lig başına ölçütler",
        "## Sıralamalar",
        "### R1 — geç bilgi",
        "### R2 — kapanış kalibrasyon hatası",
        "## Aday ligler",
        "## Raporun ölçmedikleri",
    ):
        assert heading in text, heading
    assert "| Keskinlik farkı (PSC) | Borsa farkı (BFEC) | Ü/A 2.5 marj |" in text
    assert "| M1 | m.1 | main | 56 |" in text
    assert "| X1 | x.1 | extra | 56 |" in text
    assert "GERİYE DÖNÜK ÜST SINIRDIR" in text
    assert "- M1" in text
    for item in (
        "2019/20 öncesi ana lig satırlarında saat yok",
        "kitap kümesi zamanla değişiyor",
        "Holdout'ta `PSC` kullanılamaz",
        "Bootstrap maçları bağımsız sayar",
    ):
        assert item in text, item
    assert "Team 0" not in text  # takım adı (ham satır) rapora giremez
    # Kilit doğrulaması holdout satırlarını okuyup özetler; ölçüme ise hiçbiri girmez (R114).
    assert "holdout satırı ölçüme girmedi" in text
    assert "okunmadı" not in text
    assert text.endswith("\n")


def test_report_prints_a_dash_for_metrics_a_league_does_not_have() -> None:
    extra_line = next(line for line in _report(SHIN_BEST).splitlines() if line.startswith("| X1"))
    # Ek ligde geç bilgi, değer sıklığı ve Ü/A üçlüsü (marj, LL, eğim) yok; PSC ve BFEC'siz
    # keskinlik ve borsa farkı da yok.
    assert extra_line.count("—") == 7


def test_a_league_that_could_not_be_measured_keeps_a_dash_row() -> None:
    # m9: ölçülemeyen lig rapordan DÜŞMEZ — N = 0 ve on dört ölçüt sütununun hepsi "—".
    lines = _report(SHIN_BEST).splitlines()
    (row,) = [line for line in lines if line.startswith("| X9 ")]
    assert row == "| X9 | x.9 | extra | 0 | " + " | ".join(["—"] * 14) + " |"
    header = next(line for line in lines if line.startswith("| Lig |"))
    assert row.count("|") == header.count("|")


def test_report_names_the_selected_method_and_flags_a_default_it_did_not_choose() -> None:
    assert "Seçilen yöntem: **shin**" in _report(SHIN_BEST)
    assert "UYARI" not in _report(SHIN_BEST)
    power_best = {"multiplicative": 0.99, "power": 0.96, "shin": 0.97}
    text = _report(power_best)
    assert "Seçilen yöntem: **power**" in text
    assert "UYARI" in text


def test_report_says_when_there_is_no_candidate() -> None:
    assert "Aday lig yok." in _report(SHIN_BEST, chosen=())


# ── Düzeltme turu 1 (R114) ─────────────────────────────────────────────────────────────────


def _population_slope(gamma: float) -> float:
    """`calibrated` tasarımının GERÇEK havuzlanmış eğimi: her fiyat kümesinde sonuçlar q = p^γ
    oranında (küme başına 30 000 maç) — örnekleme gürültüsü yok. γ'ya yakın ama eşit değil."""
    probs: list[tuple[float, ...]] = []
    outcomes: list[int] = []
    for home in FAIR_HOMES:
        fair = np.array((home, 0.25, 0.75 - home))
        true = fair**gamma / np.sum(fair**gamma)
        for outcome, share in enumerate(true):
            copies = round(float(share) * 30_000)
            probs.extend([tuple(float(p) for p in fair)] * copies)
            outcomes.extend([outcome] * copies)
    return calibration(probs, outcomes).slope


@pytest.mark.parametrize("gamma", (0.6, 1.5), ids=("asiri-emin", "cekingen"))
def test_slope_interval_brackets_a_known_calibration_slope_at_95_percent(gamma: float) -> None:
    # Sonuçlar p^γ'dan çekilir: gerçek eğim bilinir. Kestirim ona yakın, aralık onu içerir.
    truth = _population_slope(gamma)
    assert truth == pytest.approx(gamma, abs=0.05)  # bozulma gerçekten eğimi değiştiriyor
    matches = calibrated(900, gamma=gamma, seed=20260923)
    result = league_efficiency(EXTRA_LEAGUE, matches, method=SHIN, resamples=200)
    assert result.slope.estimate == pytest.approx(truth, abs=0.15)
    assert result.slope.low < truth < result.slope.high
    # Genişlik bağımsız bir başvuruyla sabitlenir: aynı tohum, maç ve sonuç BİRLİKTE yeniden
    # örneklenir, %2.5–%97.5 yüzdelikleri. Hizasız örnekleme ya da dar düzey (%90, %80) tutmaz.
    probs, outcomes = _closing_probs(matches, SHIN), _results(matches)
    rng = np.random.default_rng(efficiency.SEED)
    slopes = []
    for _ in range(200):
        picked = rng.integers(0, len(matches), size=len(matches))
        refit = calibration([probs[i] for i in picked], [outcomes[i] for i in picked])
        slopes.append(refit.slope)
    low, high = np.percentile(slopes, [2.5, 97.5])
    assert (result.slope.low, result.slope.high) == pytest.approx((low, high))


@pytest.mark.parametrize("count", (1, 2, 3))
def test_a_thin_league_is_unmeasurable_and_keeps_its_n(count: int) -> None:
    # R114/I3: AvgC'si tam 1–3 maçta kalibrasyon kurulamaz; düz ValueError raporu düşürürdü.
    # 1–2 maçta ana fit ayrışır; 3 maçta ana fit kurulur ama üretim tekrar sayısında (2000)
    # bir yeniden örnek ayrışır — iki yol da aynı istisnaya çıkar. Bu yüzden varsayılan tekrar.
    # R115/N1: pencerede AvgC'siz bir geliştirme maçı daha var — N onu SAYMAZ.
    thin = synthetic(count, league="X1", season="2023")
    bare = replace(synthetic(1, league="X1", season="2023", first=50)[0], odds=MappingProxyType({}))
    with pytest.raises(Unmeasurable, match="X1") as caught:
        league_efficiency(EXTRA_LEAGUE, (*thin, bare), method=SHIN)
    assert caught.value.n == count
    assert not isinstance(caught.value, NoClosingPrices)


def test_a_league_without_closing_prices_is_unmeasurable_with_n_zero() -> None:
    bare = tuple(replace(match, odds=MappingProxyType({})) for match in BASE)
    with pytest.raises(Unmeasurable) as caught:
        league_efficiency(MAIN_LEAGUE, bare, method=SHIN, resamples=FAST)
    assert isinstance(caught.value, NoClosingPrices)
    assert caught.value.n == 0


def test_an_unmeasurable_league_row_shows_its_n_and_dashes() -> None:
    main = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=FAST)
    text = render_report(
        (main,),
        rank((main,)),
        scores=SHIN_BEST,
        candidates=(),
        generated_at=datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
        unmeasured=(UNMEASURED,),
        unmeasured_counts=MappingProxyType({"X9": 2}),
    )
    (row,) = [line for line in text.splitlines() if line.startswith("| X9 ")]
    assert row == "| X9 | x.9 | extra | 2 | " + " | ".join(["—"] * 14) + " |"


def test_a_slope_interval_containing_one_is_tier_c_only_when_its_far_end_is_below_the_median() -> (
    None
):
    # Uzaklık medyanı 0.1 (tahminler 0.4, 0.2, 0, 0). 1'i içeren iki aralığın alt ucu 0 → A olamaz;
    # kademeyi ÜST uç, yani 1'den en uzak uç belirler: S1'in max(0.05, 0.4) = 0.4 → B,
    # S2'nin max(0.02, 0.05) = 0.05 → C. Yakın uç (min) S1'i de C yapardı.
    rows = (
        _row("Q1", kind=EXTRA, slope=(0.6, 0.5, 0.7)),
        _row("Q3", kind=EXTRA, slope=(1.2, 1.15, 1.25)),
        _row("S1", kind=EXTRA, slope=(1.0, 0.95, 1.4)),
        _row("S2", kind=EXTRA, slope=(1.0, 0.98, 1.05)),
    )
    assert dict(rank(rows).tiers) == {"Q1": "A", "Q3": "A", "S1": "B", "S2": "C"}


def test_distance_of_an_interval_starting_exactly_at_one() -> None:
    # Sınır: alt uç tam 1.0 iken iki dal da [0, high − 1] verir (R7 `>` ↔ `>=` eşdeğer mutant).
    assert efficiency._distance(Interval(1.1, 1.0, 1.3)) == Interval(
        pytest.approx(0.1), 0.0, pytest.approx(0.3)
    )


def test_book_gap_coverage_counts_matches_without_avgc_in_the_denominator() -> None:
    # Doluluk paydası sezonun BÜTÜN geliştirme maçlarıdır, yalnız AvgC'si tam olanlar değil:
    # 17 maçta AvgC + PSC, 3 maçta yalnız PSC → 17/20 = %85, sezon girmez.
    full = synthetic(20, start=date(2021, 8, 7), season="2122", first=20)
    thin = synthetic(20, start=date(2022, 8, 6), season="2223", first=40)
    sharp = {("PS", H2H, CLOSING): (1.9, 3.8, 3.8)}
    no_average = tuple(
        with_prices(replace(match, odds=MappingProxyType({})), sharp) for match in thin[17:]
    )
    matches = (*added(full, sharp), *added(thin[:17], sharp), *no_average)
    result = league_efficiency(MAIN_LEAGUE, matches, method=SHIN, resamples=FAST)
    used = added(full, sharp)
    average = per_match_log_loss(_closing_probs(used, SHIN), _results(used))
    keen = per_match_log_loss(_closing_probs(used, SHIN, book="PS"), _results(used))
    assert result.sharp_gap is not None
    expected = math.fsum(a - s for a, s in zip(average, keen, strict=True)) / len(used)
    assert result.sharp_gap.estimate == pytest.approx(expected)


# ── Düzeltme turu 2 (R115): yalnız kalibrasyon fiti "ölçülemez"e döner ──────────────────────


def test_resamples_below_one_is_an_error_not_an_unmeasurable_league() -> None:
    with pytest.raises(ValueError, match="yeniden örnekleme") as caught:
        league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=0)
    assert not isinstance(caught.value, Unmeasurable)


def test_invalid_probabilities_propagate_instead_of_becoming_unmeasurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Toplamı 1.5 olan olasılık satırı bir hatadır, ince lig değil: girdiyi doğrulayan ölçüt onu
    # fit'ten ÖNCE ve yakalamanın dışında reddeder.
    monkeypatch.setattr(efficiency, "match_probs", lambda match, **options: (0.5, 0.5, 0.5))
    with pytest.raises(ValueError) as caught:
        league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=FAST)
    assert not isinstance(caught.value, Unmeasurable)


def test_a_main_league_whose_totals_fit_separates_is_unmeasurable() -> None:
    # Ü/A 2.5 fiti de `_fit`ten geçer: tek maçlık Ü/A örneği ayrışır → lig ölçülemez (düz
    # ValueError raporu düşürürdü). N yine 1X2'ninkidir.
    totals = (with_prices(BASE[0], {("Avg", TOTALS_25, CLOSING): TOTAL_SETS[0]}), *BASE[1:])
    with pytest.raises(Unmeasurable, match="M1") as caught:
        league_efficiency(MAIN_LEAGUE, totals, method=SHIN, resamples=FAST)
    assert caught.value.n == 56
