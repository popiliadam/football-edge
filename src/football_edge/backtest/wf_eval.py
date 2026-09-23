"""Walk-forward değerlendirmesi (Faz 3 tasarımı §5.2–5.3, §6.3–6.5; R129, R137, R139).

Havuz ağırlığı lig başına genişleyen sezon katlarıyla: E'nin sezonu `s` için ağırlık YALNIZ E'nin
`s`'den önceki sezonlarının satırlarıyla fit edilir; E'nin ilk sezonu S'nin satırlarını kullanır.
Ligin eğitim satırı `LEAGUE_MIN_MATCHES`ın altındaysa aynı kural bütün ana liglerin havuzuyla, o da
`MIN_FIT_MATCHES`ın altındaysa yalnız piyasa `(1, 0, 0)`. Eşik gürültüye karşıdır: üç ağırlığın
örneklem dışı bedeli ~ 3 / 2n; tek ligin bir sezonu (~380 maç) bunu W1'in δ'sının üstüne çıkarır.
Karşılaştırmalar ORTAK satırlarda (bütün bileşenleri olan maçlar) yapılır: aynı maç kümesi.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from football_edge.backtest.walkforward import (
    BLEND_COMPONENTS,
    DC,
    ELO,
    EVALUATION,
    MARKET,
    SELECTION,
    Row,
)
from football_edge.history.catalog import EXTRA, MAIN
from football_edge.market.metrics import (
    Calibration,
    Interval,
    bootstrap_mean,
    brier,
    calibration,
    clv,
    per_match_log_loss,
    rps,
)
from football_edge.model.pool import NotConverged, TooFewMatches, fit_weights, pool

BLEND = "blend"
CLOSING_NAME = "closing"
MARKET_ONLY: tuple[float, ...] = (1.0, 0.0, 0.0)
LEAGUE_MIN_MATCHES = 1000
Weights = Mapping[tuple[str, str], tuple[float, ...]]  # (lig, sezon) → ağırlık


@dataclass(frozen=True)
class Score:
    name: str
    n: int
    log_loss: Interval
    brier: float
    rps: float | None  # yalnız 1X2 (sıralı üç sonuç)
    calibration: Calibration | None  # yakınsamazsa None (ölçülemedi)
    clv: Interval | None
    bets: int


@dataclass(frozen=True)
class Summary:
    main: Mapping[str, Score]  # E, ana ligler, ortak satırlar: market, elo_fit, dixon_coles, blend
    blend_gap: Interval | None  # LL(blend) − LL(market), eşleştirilmiş
    component_gaps: Mapping[str, Interval]  # her bileşen: LL(bileşen) − LL(market), ortak satırlar
    league_gaps: Mapping[str, Interval]
    extra: Mapping[str, Score]  # E, ek ligler: elo_fit, dixon_coles, closing (kıyas)
    totals: Mapping[str, Score]  # E, ana ligler, Ü/A 2.5: market, dixon_coles
    totals_gap: Interval | None  # Ü/A 2.5: LL(dixon_coles) − LL(market), eşleştirilmiş
    clv_sensitivity: Mapping[float, Interval | None]  # τ → harman CLV'si
    rows: int
    incomplete: int  # bileşeni eksik E satırı (ortak kümeye girmedi)
    fallback: tuple[str, ...]  # havuzlanmış ya da yalnız piyasa ağırlığı alan (lig, sezon)


def complete(row: Row, names: Sequence[str] = BLEND_COMPONENTS) -> bool:
    return all(name in row.components for name in names)


def _fit_or_none(rows: Sequence[Row]) -> tuple[float, ...] | None:
    """Fit edilemeyen ağırlık (az maç ya da yakınsamama) None'dır: çağıran geri düşer ve sayar.

    Yakınsamama açılıştan SONRA çıplak `ValueError`la exit 14 olurdu (16a)."""
    try:
        return fit_weights(
            [[row.components[name] for name in BLEND_COMPONENTS] for row in rows],
            [row.outcome for row in rows],
        )
    except (TooFewMatches, NotConverged):
        return None


def _training(rows: Sequence[Row], season: str) -> list[Row]:
    earlier = [row for row in rows if row.zone == EVALUATION and row.season < season]
    return earlier or [row for row in rows if row.zone == SELECTION]


def fold_weights(rows: Sequence[Row]) -> tuple[Weights, tuple[str, ...]]:
    """(lig, E sezonu) → ağırlık ve geri düşülen anahtarlar; yalnız ana ligler ve tam satırlar."""
    usable = [row for row in rows if row.kind == MAIN and complete(row)]
    weights: dict[tuple[str, str], tuple[float, ...]] = {}
    fallback: list[str] = []
    for league in sorted({row.key.league for row in usable}):
        own = [row for row in usable if row.key.league == league]
        seasons = sorted({row.season for row in own if row.zone == EVALUATION})
        for season in seasons:
            training = _training(own, season)
            found = _fit_or_none(training) if len(training) >= LEAGUE_MIN_MATCHES else None
            if found is None:
                fallback.append(f"{league}/{season}")
                found = _fit_or_none(_training(usable, season)) or MARKET_ONLY
            weights[(league, season)] = found
    return MappingProxyType(weights), tuple(fallback)


def frozen_weights(
    rows: Sequence[Row], targets: Sequence[tuple[str, str]]
) -> tuple[Weights, tuple[str, ...]]:
    """Geliştirme satırlarının BÜTÜN E'siyle fit edilmiş ağırlık, verilen (lig, sezon) için —
    holdout ve sonrası dönemi ağırlığı hiç görmez (`final_eval`)."""
    usable = [row for row in rows if row.kind == MAIN and complete(row) and row.zone == EVALUATION]
    weights: dict[tuple[str, str], tuple[float, ...]] = {}
    fallback: list[str] = []
    pooled = _fit_or_none(usable) or MARKET_ONLY
    for league, season in sorted(set(targets)):
        own = [row for row in usable if row.key.league == league]
        found = _fit_or_none(own) if len(own) >= LEAGUE_MIN_MATCHES else None
        if found is None:
            fallback.append(f"{league}/{season}")
            found = pooled
        weights[(league, season)] = found
    return MappingProxyType(weights), tuple(fallback)


def blended(rows: Sequence[Row], weights: Weights) -> tuple[tuple[Row, tuple[float, ...]], ...]:
    return tuple(
        (
            row,
            pool(
                [row.components[name] for name in BLEND_COMPONENTS],
                weights[(row.key.league, row.season)],
            ),
        )
        for row in rows
        if (row.key.league, row.season) in weights and complete(row)
    )


def bet_clv(
    probs: Sequence[float],
    pre: Sequence[float] | None,
    closing: Sequence[float] | None,
    tau: float,
) -> float | None:
    """Sabit kural (§6.4): en büyük `p · o − 1` sonucu, eşiği aşıyorsa; CLV kapanışa karşı."""
    if pre is None or closing is None:
        return None
    values = [p * o - 1.0 for p, o in zip(probs, pre, strict=True)]
    pick = max(range(len(values)), key=values.__getitem__)
    if values[pick] <= tau:
        return None
    return clv(pre[pick], closing[pick])


def _calibration(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> Calibration | None:
    try:
        return calibration(probs, outcomes)
    except ValueError:
        return None


def score(
    name: str,
    probs: Sequence[Sequence[float]],
    outcomes: Sequence[int],
    clvs: Sequence[float],
    *,
    resamples: int,
) -> Score:
    return Score(
        name=name,
        n=len(probs),
        log_loss=bootstrap_mean(per_match_log_loss(probs, outcomes), resamples=resamples),
        brier=brier(probs, outcomes),
        rps=rps(probs, outcomes) if len(probs[0]) == 3 else None,
        calibration=_calibration(probs, outcomes),
        clv=bootstrap_mean(clvs, resamples=resamples) if clvs else None,
        bets=len(clvs),
    )


def _clvs(pairs: Sequence[tuple[Row, Sequence[float]]], tau: float) -> list[float]:
    found = [bet_clv(probs, row.pre, row.closing, tau) for row, probs in pairs]
    return [value for value in found if value is not None]


def _gap(
    first: Sequence[Sequence[float]],
    second: Sequence[Sequence[float]],
    outcomes: Sequence[int],
    resamples: int,
) -> Interval:
    a = per_match_log_loss(first, outcomes)
    b = per_match_log_loss(second, outcomes)
    return bootstrap_mean([x - y for x, y in zip(a, b, strict=True)], resamples=resamples)


def _component_gaps(
    pairs: Sequence[tuple[Row, tuple[float, ...]]], resamples: int
) -> dict[str, Interval]:
    """Ortak satırlarda bulunan her bileşenin piyasaya karşı eşleştirilmiş ΔLL'si (C2; 16c)."""
    if not pairs:
        return {}
    outcomes = [row.outcome for row, _ in pairs]
    market = [row.components[MARKET] for row, _ in pairs]
    names = sorted(set.intersection(*(set(row.components) for row, _ in pairs)) - {MARKET})
    return {
        name: _gap([row.components[name] for row, _ in pairs], market, outcomes, resamples)
        for name in names
    }


def _totals_gap(rows: Sequence[Row], resamples: int) -> Interval | None:
    """Ü/A 2.5: DC − piyasa, ikisi de olan satırlarda eşleştirilmiş (C5; 16c)."""
    usable = [row for row in rows if MARKET in row.totals and DC in row.totals]
    if not usable:
        return None
    return _gap(
        [row.totals[DC] for row in usable],
        [row.totals[MARKET] for row in usable],
        [row.totals_outcome for row in usable],
        resamples,
    )


def _main_scores(
    pairs: Sequence[tuple[Row, tuple[float, ...]]], tau: float, resamples: int
) -> dict[str, Score]:
    """Harman ve bütün satırlarda bulunan her bileşen (ör. `final_eval`in iskele Elo'su)."""
    outcomes = [row.outcome for row, _ in pairs]
    names = sorted(set.intersection(*(set(row.components) for row, _ in pairs)))
    found: dict[str, Score] = {}
    for name in names:
        column = [(row, row.components[name]) for row, _ in pairs]
        found[name] = score(
            name, [p for _, p in column], outcomes, _clvs(column, tau), resamples=resamples
        )
    found[BLEND] = score(
        BLEND, [p for _, p in pairs], outcomes, _clvs(pairs, tau), resamples=resamples
    )
    return found


def _extra_scores(rows: Sequence[Row], resamples: int) -> dict[str, Score]:
    usable = [row for row in rows if complete(row, (ELO, DC)) and row.closing is not None]
    if not usable:
        return {}
    outcomes = [row.outcome for row in usable]
    found = {
        name: score(
            name, [row.components[name] for row in usable], outcomes, (), resamples=resamples
        )
        for name in (ELO, DC)
    }
    closing = [row.closing for row in usable if row.closing is not None]
    found[CLOSING_NAME] = score(CLOSING_NAME, closing, outcomes, (), resamples=resamples)
    return found


def _totals_scores(rows: Sequence[Row], tau: float, resamples: int) -> dict[str, Score]:
    usable = [row for row in rows if MARKET in row.totals and DC in row.totals]
    if not usable:
        return {}
    outcomes = [row.totals_outcome for row in usable]
    found: dict[str, Score] = {}
    for name in (MARKET, DC):
        clvs = [
            bet_clv(row.totals[name], row.totals_pre, row.totals_closing, tau) for row in usable
        ]
        found[name] = score(
            name,
            [row.totals[name] for row in usable],
            outcomes,
            [value for value in clvs if value is not None],
            resamples=resamples,
        )
    return found


def summarise(
    rows: Sequence[Row],
    *,
    tau: float,
    sensitivity: Sequence[float],
    resamples: int,
    zone: str = EVALUATION,
    given: tuple[Weights, tuple[str, ...]] | None = None,
) -> Summary:
    """`zone` bölgesinin özeti; ağırlık verilmezse genişleyen katlar (`fold_weights`)."""
    weights, fallback = fold_weights(rows) if given is None else given
    evaluation = [row for row in rows if row.zone == zone]
    main = [row for row in evaluation if row.kind == MAIN]
    pairs = blended(main, weights)
    outcomes = [row.outcome for row, _ in pairs]
    market = [row.components[MARKET] for row, _ in pairs]
    leagues = sorted({row.key.league for row, _ in pairs})
    return Summary(
        main=MappingProxyType(_main_scores(pairs, tau, resamples) if pairs else {}),
        blend_gap=_gap([p for _, p in pairs], market, outcomes, resamples) if pairs else None,
        component_gaps=MappingProxyType(_component_gaps(pairs, resamples)),
        league_gaps=MappingProxyType(
            {
                league: _gap(
                    [p for row, p in pairs if row.key.league == league],
                    [row.components[MARKET] for row, _ in pairs if row.key.league == league],
                    [row.outcome for row, _ in pairs if row.key.league == league],
                    resamples,
                )
                for league in leagues
            }
        ),
        extra=MappingProxyType(
            _extra_scores([row for row in evaluation if row.kind == EXTRA], resamples)
        ),
        totals=MappingProxyType(_totals_scores(main, tau, resamples)),
        totals_gap=_totals_gap(main, resamples),
        clv_sensitivity=MappingProxyType(
            {
                value: (
                    bootstrap_mean(found, resamples=resamples)
                    if (found := _clvs(pairs, value))
                    else None
                )
                for value in sensitivity
            }
        ),
        rows=len(evaluation),
        incomplete=sum(1 for row in main if not complete(row)),
        fallback=fallback,
    )
