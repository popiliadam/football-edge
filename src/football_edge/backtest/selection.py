"""Hiperparametre seçimi — yalnız S bölgesinde (Faz 3 tasarımı §5.2, §6.1–6.2; R129).

Koordinat inişi: iskele değerlerden başlanır, parametreler SABİT sırayla tek tek ızgarada denenir,
her birinde en düşük S log loss'u tutulur; tek tur. Elo'nun beraberlik payı `δ` her adayda S'nin
beklentileri üzerinde kapalı biçimde fit edilir (`fit_draw`). E ve holdout hiçbir adımda okunmaz.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from types import MappingProxyType
from typing import Any, TypeVar

from football_edge.backtest.harness import Strategy
from football_edge.backtest.walkforward import (
    DC,
    ELO,
    EXTRA_SELECTION,
    MAIN_SELECTION,
    SELECTION,
    Row,
    group_kind,
    group_rows,
)
from football_edge.history.catalog import MAIN
from football_edge.history.types import HistMatch
from football_edge.market.metrics import LOG_FLOOR
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import (
    LINEAR_MARGIN,
    LOG_MARGIN,
    NO_MARGIN,
    ORDERED,
    QUADRATIC,
    EloModel,
    EloModelConfig,
    elo_outcome_probs,
    expectation,
    fit_outcome_params,
)
from football_edge.model.strategies import DixonColesStrategy

ELO_GRID: Mapping[str, tuple[Any, ...]] = MappingProxyType(
    {
        "k": (10.0, 15.0, 20.0, 25.0, 30.0),
        "home_advantage": (40.0, 65.0, 90.0),
        "margin": (NO_MARGIN, LINEAR_MARGIN, LOG_MARGIN),
        "regress": (0.0, 0.2, 0.4),
        "newcomer_offset": (0.0, 75.0, 150.0),
        # R142: beraberlik eşlemesi kategorik bir hiperparametredir; S seçer, yalnız seçilen donar.
        "draw_form": (QUADRATIC, ORDERED),
    }
)
DC_GRID: Mapping[str, tuple[Any, ...]] = MappingProxyType(
    {"xi": (0.0010, 0.0019, 0.0030), "ridge": (0.003, 0.01, 0.03)}
)
Groups = Mapping[str, Sequence[HistMatch]]
T = TypeVar("T")


@dataclass(frozen=True)
class Trial:
    model: str
    params: Mapping[str, Any]
    log_loss: float


def coordinate_descent(
    start: T, grid: Mapping[str, tuple[Any, ...]], loss: Callable[[T], float]
) -> tuple[T, tuple[tuple[Mapping[str, Any], float], ...]]:
    """Tek tur; aynı aday iki kez ölçülmez. Eşitlikte önce denenen (ızgara sırası) kalır."""
    seen: dict[tuple[tuple[str, Any], ...], float] = {}
    trace: list[tuple[Mapping[str, Any], float]] = []

    def measure(candidate: T) -> float:
        key = tuple((name, getattr(candidate, name)) for name in grid)
        if key not in seen:
            seen[key] = loss(candidate)
            trace.append((MappingProxyType(dict(key)), seen[key]))
        return seen[key]

    best = start
    best_loss = measure(start)
    for name in grid:
        for value in grid[name]:
            candidate = replace(best, **{name: value})  # type: ignore[type-var]
            found = measure(candidate)
            if found < best_loss:
                best, best_loss = candidate, found
    return best, tuple(trace)


def _before_selection_end(
    matches: Sequence[HistMatch], kinds: Mapping[str, str]
) -> tuple[HistMatch, ...]:
    end = (MAIN_SELECTION if group_kind(matches, kinds) == MAIN else EXTRA_SELECTION).end
    return tuple(match for match in matches if match.date < end)


def active_from(matches: Sequence[HistMatch], kinds: Mapping[str, str]) -> date | None:
    window = MAIN_SELECTION if group_kind(matches, kinds) == MAIN else EXTRA_SELECTION
    return window.start


def _selection_rows(
    groups: Groups,
    kinds: Mapping[str, str],
    build: Callable[[Sequence[HistMatch]], Mapping[str, Strategy]],
    method: str,
) -> list[Row]:
    return [
        row
        for matches in groups.values()
        for row in group_rows(matches, kinds, build(matches), method=method)
        if row.zone == SELECTION
    ]


def elo_loss(
    groups: Groups,
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: EloModelConfig,
    *,
    method: str,
) -> tuple[float, EloModelConfig]:
    """(S log loss'u, adayın beraberlik parametreleri S'de fit edilmiş hâli).

    Aday `quadratic` biçimle oynatılır: reyting yolu beraberlik biçiminden bağımsızdır ve E bu
    biçimde tahminden tam geri okunur (`expectation`); adayın kendi biçimi E'de fit edilir (R142).
    """
    replayed = replace(config, draw_form=QUADRATIC)
    rows = [
        row
        for row in _selection_rows(
            groups, kinds, lambda _: {ELO: EloModel(config=replayed, groups=rating_groups)}, method
        )
        if ELO in row.components
    ]
    expectations = [expectation(row.components[ELO]) for row in rows]
    outcomes = [row.outcome for row in rows]
    fitted = fit_outcome_params(config, expectations, outcomes)
    loss = -math.fsum(
        math.log(max(elo_outcome_probs(e, fitted)[o], LOG_FLOOR))
        for e, o in zip(expectations, outcomes, strict=True)
    ) / len(rows)
    return loss, fitted


def dc_loss(
    groups: Groups,
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: DCConfig,
    *,
    cadence_days: int,
    method: str,
) -> float:
    def build(matches: Sequence[HistMatch]) -> Mapping[str, Strategy]:
        return {
            DC: DixonColesStrategy(
                config=config,
                groups=rating_groups,
                active_from=active_from(matches, kinds),
                cadence_days=cadence_days,
            )
        }

    rows = [row for row in _selection_rows(groups, kinds, build, method) if DC in row.components]
    return -math.fsum(
        math.log(max(row.components[DC][row.outcome], LOG_FLOOR)) for row in rows
    ) / len(rows)


def select(
    groups: Groups,
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    *,
    cadence_days: int,
    method: str,
) -> tuple[EloModelConfig, DCConfig, tuple[Trial, ...]]:
    # S satırlarının tahmini yalnız S'nin sonundan önceki sonuçlara bağlıdır: E'yi oynatmak boşa
    # (plan incelemesi m6 — DC her adayda E'yi de fit ederdi).
    groups = MappingProxyType(
        {name: _before_selection_end(matches, kinds) for name, matches in groups.items() if matches}
    )
    fitted: dict[EloModelConfig, EloModelConfig] = {}

    def elo_objective(candidate: EloModelConfig) -> float:
        loss, fitted[candidate] = elo_loss(groups, kinds, rating_groups, candidate, method=method)
        return loss

    elo, elo_trace = coordinate_descent(EloModelConfig(), ELO_GRID, elo_objective)
    dc, dc_trace = coordinate_descent(
        DCConfig(),
        DC_GRID,
        lambda candidate: dc_loss(
            groups, kinds, rating_groups, candidate, cadence_days=cadence_days, method=method
        ),
    )
    trials = tuple(Trial("elo", params, loss) for params, loss in elo_trace) + tuple(
        Trial("dixon_coles", params, loss) for params, loss in dc_trace
    )
    return fitted[elo], dc, trials
