"""Bilinen sonuçlar (tasarım §11, D13): harness ve vig hattı literatürün yönsel sonuçlarını üretir.

Yalnız geliştirme dönemi okunur: önce `select_periods` (DEV), sonra lig türünün penceresi (ana:
`MAIN_WINDOW`, ek: `EXTRA_WINDOW`). Kapı: K1, K3, K4. Rapor: K2 (vig yöntemi seçimi) ve D1 (karar
anı kuralının dolaylı sınaması, tasarım §4.5). Ölçülemeyen denetim GEÇMEZ — "ölçülemedi" yazar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from itertools import pairwise

from football_edge.backtest.evaluate import DEFAULT_RESAMPLES, clv_values
from football_edge.backtest.harness import replay
from football_edge.backtest.strategies import Placebo
from football_edge.backtest.timeline import decision_at
from football_edge.history.holdout import DEV, EXTRA_WINDOW, MAIN_WINDOW, in_window, select_periods
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, HistMatch
from football_edge.market.devig import METHODS, MULTIPLICATIVE, POWER, SHIN, devig, match_probs
from football_edge.market.metrics import (
    Interval,
    bootstrap_mean,
    log_loss,
    outcome_index,
    per_match_log_loss,
)

K1_MIN_POSITIVE = 18
K3_MIN_COVERAGE = 0.9
DRIFT_BUCKETS: tuple[tuple[float, float], ...] = ((0, 12), (12, 36), (36, 60), (60, 96))
REFERENCE_BOOK = "Avg"
SHARP_BOOK = "PS"

Quote = tuple[str, str]  # (kitap, evre)
Leagues = Mapping[str, Sequence[HistMatch]]
PRE_AVG: Quote = (REFERENCE_BOOK, PRE_CLOSING)
CLOSE_AVG: Quote = (REFERENCE_BOOK, CLOSING)
CLOSE_SHARP: Quote = (SHARP_BOOK, CLOSING)


@dataclass(frozen=True)
class Check:
    id: str
    gate: bool
    passed: bool
    detail: str


def _unmeasured(check_id: str, *, gate: bool, reason: str) -> Check:
    return Check(id=check_id, gate=gate, passed=False, detail=f"{check_id} ölçülemedi: {reason}")


def _interval(interval: Interval) -> str:
    return f"{interval.estimate:.4f} [%95 {interval.low:.4f}, {interval.high:.4f}]"


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _all(leagues: Leagues) -> tuple[HistMatch, ...]:
    return tuple(match for code in sorted(leagues) for match in leagues[code])


def _probs(match: HistMatch, quote: Quote, method: str) -> tuple[float, ...] | None:
    book, phase = quote
    return match_probs(match, book=book, market=H2H, phase=phase, method=method)


def _gaps(
    matches: Sequence[HistMatch], first: Quote, second: Quote, method: str
) -> tuple[float, ...]:
    """İki fiyat kümesi de tam olan maçlarda maç başına LL(first) − LL(second)."""
    firsts: list[tuple[float, ...]] = []
    seconds: list[tuple[float, ...]] = []
    outcomes: list[int] = []
    for match in matches:
        a, b = _probs(match, first, method), _probs(match, second, method)
        if a is None or b is None:
            continue
        firsts.append(a)
        seconds.append(b)
        outcomes.append(outcome_index(match, H2H))
    if not outcomes:
        return ()
    first_ll = per_match_log_loss(firsts, outcomes)
    second_ll = per_match_log_loss(seconds, outcomes)
    return tuple(x - y for x, y in zip(first_ll, second_ll, strict=True))


def _k1(main: Leagues, *, method: str, main_codes: frozenset[str], resamples: int) -> Check:
    gaps = {code: _gaps(main.get(code, ()), PRE_AVG, CLOSE_AVG, method) for code in main_codes}
    pooled = [gap for code in sorted(gaps) for gap in gaps[code]]
    if not pooled:
        return _unmeasured(
            "K1", gate=True, reason="kapanış öncesi Avg ve kapanış AvgC 1X2'si birlikte tam maç yok"
        )
    interval = bootstrap_mean(pooled, resamples=resamples)
    positive = sum(1 for values in gaps.values() if values and _mean(values) > 0)
    detail = (
        f"ΔLL = LL(kapanış öncesi Avg) − LL(kapanış AvgC) {_interval(interval)} n={len(pooled)}; "
        f"ΔLL > 0 olan ana lig {positive}/{len(main_codes)} (eşik {K1_MIN_POSITIVE})"
    )
    passed = interval.low > 0 and positive >= K1_MIN_POSITIVE
    return Check(id="K1", gate=True, passed=passed, detail=detail)


def _all_methods(match: HistMatch) -> dict[str, tuple[float, ...]] | None:
    probs = {method: _probs(match, CLOSE_AVG, method) for method in METHODS}
    complete = {method: value for method, value in probs.items() if value is not None}
    return complete if len(complete) == len(METHODS) else None


def _k2(windowed: Leagues) -> Check:
    by_method: dict[str, list[tuple[float, ...]]] = {method: [] for method in METHODS}
    outcomes: list[int] = []
    for match in _all(windowed):
        probs = _all_methods(match)
        if probs is None:
            continue
        outcomes.append(outcome_index(match, H2H))
        for method in METHODS:
            by_method[method].append(probs[method])
    if not outcomes:
        return _unmeasured("K2", gate=False, reason="kapanış AvgC 1X2'si tam maç yok")
    scores = {method: log_loss(by_method[method], outcomes) for method in METHODS}
    listed = " · ".join(f"{method} {scores[method]:.5f}" for method in METHODS)
    passed = min(scores[SHIN], scores[POWER]) < scores[MULTIPLICATIVE]
    detail = f"kapanış AvgC havuzlanmış log loss n={len(outcomes)}: {listed}"
    return Check(id="K2", gate=False, passed=passed, detail=detail)


def _both_closings(match: HistMatch) -> bool:
    return all(
        match.prices(book, H2H, CLOSING) is not None for book in (REFERENCE_BOOK, SHARP_BOOK)
    )


def _league_seasons(windowed: Leagues) -> dict[tuple[str, str], list[HistMatch]]:
    groups: dict[tuple[str, str], list[HistMatch]] = {}
    for code in sorted(windowed):
        for match in windowed[code]:
            groups.setdefault((code, match.season), []).append(match)
    return groups


def _k3(windowed: Leagues, *, method: str, resamples: int) -> Check:
    seasons = _league_seasons(windowed)
    kept = [
        matches
        for matches in seasons.values()
        if sum(map(_both_closings, matches)) / len(matches) >= K3_MIN_COVERAGE
    ]
    gaps = [gap for matches in kept for gap in _gaps(matches, CLOSE_AVG, CLOSE_SHARP, method)]
    if not gaps:
        return _unmeasured(
            "K3", gate=True, reason="AvgC ve PSC 1X2'sinin birlikte %90 dolu olduğu lig-sezon yok"
        )
    interval = bootstrap_mean(gaps, resamples=resamples)
    detail = (
        f"ΔLL = LL(AvgC) − LL(PSC) {_interval(interval)} n={len(gaps)}; lig-sezon "
        f"{len(kept)}/{len(seasons)} (AvgC ve PSC birlikte ≥ %90 dolu)"
    )
    return Check(id="K3", gate=True, passed=interval.low > 0, detail=detail)


def _k4(main: Leagues, *, method: str, resamples: int) -> Check:
    # Yalnız CLV: kalibrasyon fiti (evaluate) ayrışan küçük örnekte haklı olarak reddeder ve K4'ü
    # ölçemez kılardı; K4'ün sorusu bahsin kapanışa göre değeridir.
    result = replay(_all(main), Placebo(devig=partial(devig, method=method)))
    counts = f"karar yok {result.no_decision}, tahmin yok {result.no_prediction}"
    bets = sum(1 for prediction in result.predictions if prediction.bet is not None)
    values = clv_values(result, method=method)
    if not values:
        return _unmeasured(
            "K4", gate=True, reason=f"kapanışı tam bahis yok ({bets} bahis; {counts})"
        )
    interval = bootstrap_mean(values, resamples=resamples)
    detail = (
        f"Placebo CLV (AvgC kapanışına karşı) {_interval(interval)} bahis={len(values)}; "
        f"kapanışı eksik {bets - len(values)}; {counts}"
    )
    return Check(id="K4", gate=True, passed=interval.high < 0, detail=detail)


def _drift(match: HistMatch, method: str) -> tuple[float, float] | None:
    """(karar → başlama saati, kapanış öncesi ile kapanış olasılıkları arasındaki TV mesafesi)."""
    if match.kickoff is None:
        return None
    decided = decision_at(match.date, match.kickoff)
    pre, close = _probs(match, PRE_AVG, method), _probs(match, CLOSE_AVG, method)
    if decided is None or pre is None or close is None:
        return None
    hours = (match.kickoff - decided).total_seconds() / 3600
    return hours, 0.5 * sum(abs(a - b) for a, b in zip(pre, close, strict=True))


def _d1(main: Leagues, *, method: str) -> Check:
    drifts = [drift for drift in (_drift(match, method) for match in _all(main)) if drift]
    parts: list[str] = []
    means: list[float] = []
    for low, high in DRIFT_BUCKETS:
        values = [distance for hours, distance in drifts if low <= hours < high]
        label = f"[{low},{high}) sa"
        if not values:
            parts.append(f"{label} —")
            continue
        means.append(_mean(values))
        parts.append(f"{label} {means[-1]:.4f} (n={len(values)})")
    if len(means) < 2:
        return _unmeasured("D1", gate=False, reason="en az iki süre kovasında maç yok")
    rising = all(a <= b for a, b in pairwise(means))
    detail = (
        "karar→başlama süresine göre ortalama TV(kapanış öncesi Avg, kapanış AvgC): "
        + " · ".join(parts)
        + f"; tekdüze artan: {'evet' if rising else 'hayır'}"
    )
    return Check(id="D1", gate=False, passed=rising, detail=detail)


def run_selftest(
    matches_by_league: Leagues,
    *,
    method: str,
    main_codes: frozenset[str],
    resamples: int = DEFAULT_RESAMPLES,
) -> tuple[Check, ...]:
    """K1, K2, K3, K4, D1 — bu sırayla. Holdout ve sonrası satırlar hiçbir denetime girmez."""
    dev = {
        code: select_periods(matches, periods=frozenset({DEV}))
        for code, matches in matches_by_league.items()
    }
    windowed = {
        code: tuple(
            match
            for match in matches
            if in_window(match, MAIN_WINDOW if code in main_codes else EXTRA_WINDOW)
        )
        for code, matches in dev.items()
    }
    main = {code: matches for code, matches in windowed.items() if code in main_codes}
    return (
        _k1(main, method=method, main_codes=main_codes, resamples=resamples),
        _k2(windowed),
        _k3(windowed, method=method, resamples=resamples),
        _k4(main, method=method, resamples=resamples),
        _d1(main, method=method),
    )
