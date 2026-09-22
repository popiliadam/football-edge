"""Olay akışı (tasarım §7.1): karar ve sonuç anları zaman sırasına dizilir.

Aynı andaki olaylarda karar ÖNCE gelir (tutucu): tam karar anında bilinen sonuç o kararda
görülmez. Akış yalnız anları ve maçın sırasını taşır — kapanış oranı ve sonuç akışa girmez.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from football_edge.backtest.timeline import decision_at, result_known_at
from football_edge.history.types import HistMatch

DECISION: int = 0
RESULT: int = 1


@dataclass(frozen=True, order=True)
class Event:
    at: datetime
    kind: int
    match_index: int


def _events_of(index: int, match: HistMatch) -> tuple[Event, ...]:
    result = Event(result_known_at(match.date, match.kickoff), RESULT, index)
    decision = decision_at(match.date, match.kickoff)
    if decision is None:
        return (result,)
    return (Event(decision, DECISION, index), result)


def build_events(matches: Sequence[HistMatch]) -> tuple[Event, ...]:
    """Her maça bir sonuç olayı, kararı olana bir karar olayı; (an, tür, sıra) düzeninde."""
    return tuple(
        sorted(event for index, match in enumerate(matches) for event in _events_of(index, match))
    )
