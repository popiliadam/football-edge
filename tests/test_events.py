"""Olay akışı: her maçın bir sonucu, varsa bir kararı; aynı anda karar önce."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from football_edge.backtest.events import DECISION, RESULT, Event, build_events
from football_edge.backtest.timeline import decision_at, result_known_at
from football_edge.history.types import HistMatch
from tests.backtest_builders import hist_match

pytestmark = pytest.mark.leakage

FRIDAY_NOON_BST = datetime(2024, 8, 9, 11, tzinfo=UTC)


def _matches() -> tuple[HistMatch, ...]:
    return (
        # cuma 09:00 BST başlıyor: kararı yok, sonucu tam cuma 12:00 BST'de bilinir
        hist_match(day=date(2024, 8, 9), kickoff=datetime(2024, 8, 9, 8, tzinfo=UTC)),
        # cumartesi maçı: kararı tam da o an (cuma 12:00 BST)
        hist_match(day=date(2024, 8, 10), kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC)),
        # saatsiz çarşamba maçı: karar salı, sonuç perşembe 03:00 Londra
        hist_match(day=date(2024, 8, 7)),
    )


def test_a_decision_sorts_before_a_result_at_the_same_instant() -> None:
    assert DECISION < RESULT
    assert Event(FRIDAY_NOON_BST, DECISION, 9) < Event(FRIDAY_NOON_BST, RESULT, 0)


def test_every_match_gets_one_result_and_a_decision_only_when_it_has_one() -> None:
    events = build_events(_matches())

    assert sorted(event.match_index for event in events if event.kind == RESULT) == [0, 1, 2]
    assert sorted(event.match_index for event in events if event.kind == DECISION) == [1, 2]


def test_event_instants_come_from_the_timeline() -> None:
    matches = _matches()

    for event in build_events(matches):
        match = matches[event.match_index]
        expected = (
            decision_at(match.date, match.kickoff)
            if event.kind == DECISION
            else result_known_at(match.date, match.kickoff)
        )
        assert event.at == expected


def test_events_run_in_time_order_with_the_decision_first_on_a_tie() -> None:
    events = build_events(_matches())

    assert list(events) == sorted(events)
    assert [(event.kind, event.match_index) for event in events] == [
        (DECISION, 2),
        (RESULT, 2),
        (DECISION, 1),  # cuma 12:00 BST — 0. maçın sonucuyla aynı an
        (RESULT, 0),
        (RESULT, 1),
    ]


def test_no_matches_make_no_events() -> None:
    assert build_events(()) == ()
