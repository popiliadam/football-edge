"""Canlı gölge tahmin (Faz 3 tasarımı §10, R134): kararı verilmiş maçların bileşen olasılıkları.

Yayın YOK. Aynı (grup, karar anı) için durum BİR kez kurulur: `observe` akışı o karardaki bütün
maçlar için aynıdır. Harman ve bahis bu satırlardan, dondurulmuş ağırlıkla sonradan hesaplanır —
satır karar anının bütün girdisini (bileşenler, kapanış öncesi fiyat) taşır.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg

from football_edge.backtest.harness import Strategy
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.walkforward import DC, ELO, MARKET
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, OddsKey
from football_edge.live.context import REFERENCE_BOOK, LiveBatch, LiveDecision, match_key_text
from football_edge.market.devig import InvalidPrices, devig
from football_edge.model.elo_model import EloModel
from football_edge.model.strategies import DixonColesStrategy

_INSERT = """
    INSERT INTO model_predictions
      (match_id, match_key, strategy, p_home, p_draw, p_away, pre_home, pre_draw, pre_away,
       decided_at, model_config_sha256, git_sha)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (match_id, strategy, model_config_sha256) DO NOTHING
"""


@dataclass(frozen=True)
class ShadowRow:
    match_id: str
    match_key: str
    strategy: str
    probs: tuple[float, float, float]
    pre: tuple[float, float, float]
    decided_at: datetime
    model_config_sha256: str
    git_sha: str


def _pre(decision: LiveDecision) -> tuple[float, float, float]:
    home, draw, away = (
        decision.record.pre_prices[OddsKey(REFERENCE_BOOK, H2H, outcome, PRE_CLOSING)]
        for outcome in RESULTS
    )
    return home, draw, away


def _market(pre: tuple[float, float, float], method: str) -> tuple[float, ...] | None:
    """Karar anı fiyatının adil olasılığı; devig reddederse (ör. Σ 1/o < 1, 16i) None."""
    try:
        return devig(pre, method)
    except InvalidPrices:
        return None


def rejected_prices(batch: LiveBatch, method: str) -> int:
    """17g: karar anı fiyatını devig'in reddettiği karar sayısı — bunlara piyasa satırı yazılmaz;
    sayı gölge satırında adıyla görünür (sessizce düşmez). Yargı `shadow_rows`unkiyle AYNI
    (`_market`): sayı ile yazılmayan piyasa satırı iki ayrı kurala ayrışamaz."""
    return sum(1 for decision in batch.decisions if _market(_pre(decision), method) is None)


def _states(
    decisions: Sequence[LiveDecision], config: ModelConfig, rating_groups: Mapping[str, str]
) -> dict[tuple[str, datetime], dict[str, Strategy]]:
    """(grup, karar anı) → gözlenmiş stratejiler; akış aynı olduğu için bir kez."""
    found: dict[tuple[str, datetime], dict[str, Strategy]] = {}
    for decision in decisions:
        slot = (
            rating_groups.get(decision.record.key.league, decision.record.key.league),
            decision.context.decision_at,
        )
        if slot in found:
            continue
        states: dict[str, Strategy] = {
            ELO: EloModel(config=config.elo, groups=rating_groups),
            DC: DixonColesStrategy(
                config=config.dixon_coles, groups=rating_groups, cadence_days=config.cadence_days
            ),
        }
        for result in decision.results:
            states = {name: state.observe(result) for name, state in states.items()}
        found[slot] = states
    return found


def shadow_rows(
    batch: LiveBatch,
    *,
    config: ModelConfig,
    rating_groups: Mapping[str, str],
    config_sha256: str,
    git_sha: str,
) -> tuple[ShadowRow, ...]:
    states = _states(batch.decisions, config, rating_groups)
    rows: list[ShadowRow] = []
    for decision in batch.decisions:
        key = decision.record.key
        pre = _pre(decision)
        found: dict[str, tuple[float, ...]] = {}
        market = _market(pre, config.method)
        if market is not None:
            found[MARKET] = market
        slot = (rating_groups.get(key.league, key.league), decision.context.decision_at)
        for name, state in states[slot].items():
            prediction = state.predict(decision.context)
            if prediction is not None:
                found[name] = prediction.probs
        rows.extend(
            ShadowRow(
                match_id=decision.match_id,
                match_key=match_key_text(key),
                strategy=name,
                probs=(probs[0], probs[1], probs[2]),
                pre=pre,
                decided_at=decision.context.decision_at,
                model_config_sha256=config_sha256,
                git_sha=git_sha,
            )
            for name, probs in sorted(found.items())
        )
    return tuple(rows)


def write_shadow(conn: psycopg.Connection[Any], rows: Sequence[ShadowRow]) -> int:
    """Satırları yazar ve commit'ler; aynı (maç, strateji, yapılandırma) ikinci kez yazılmaz."""
    written = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                _INSERT,
                (
                    row.match_id,
                    row.match_key,
                    row.strategy,
                    *row.probs,
                    *row.pre,
                    row.decided_at,
                    row.model_config_sha256,
                    row.git_sha,
                ),
            )
            written += max(cur.rowcount, 0)
    conn.commit()
    return written
