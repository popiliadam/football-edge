"""Zaman semantiği: karar anı ve sonucun bilindiği an (tasarım §4.5, D4, D5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest

from football_edge.backtest.timeline import (
    DECISION_HOUR,
    LONDON,
    RESULT_LAG,
    decision_at,
    result_known_at,
)

pytestmark = pytest.mark.leakage


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_constants_pin_london_noon_and_a_three_hour_lag() -> None:
    assert LONDON.key == "Europe/London"
    assert DECISION_HOUR == 12
    assert timedelta(hours=3) == RESULT_LAG


@pytest.mark.parametrize(
    ("match_date", "decided"),
    [
        (date(2024, 8, 5), _utc(2024, 8, 2, 11)),  # pazartesi → önceki cuma
        (date(2024, 8, 6), _utc(2024, 8, 6, 11)),  # salı → aynı gün
        (date(2024, 8, 7), _utc(2024, 8, 6, 11)),  # çarşamba → salı
        (date(2024, 8, 8), _utc(2024, 8, 6, 11)),  # perşembe → salı
        (date(2024, 8, 9), _utc(2024, 8, 9, 11)),  # cuma → aynı gün
        (date(2024, 8, 10), _utc(2024, 8, 9, 11)),  # cumartesi → cuma
        (date(2024, 8, 11), _utc(2024, 8, 9, 11)),  # pazar → cuma
    ],
    ids=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
)
def test_every_weekday_maps_to_friday_or_tuesday_noon_london_in_summer(
    match_date: date, decided: datetime
) -> None:
    assert decision_at(match_date, None) == decided


@pytest.mark.parametrize(
    ("match_date", "decided"),
    [
        (date(2024, 1, 15), _utc(2024, 1, 12, 12)),  # pazartesi → cuma
        (date(2024, 1, 17), _utc(2024, 1, 16, 12)),  # çarşamba → salı
        (date(2024, 1, 20), _utc(2024, 1, 19, 12)),  # cumartesi → cuma
    ],
    ids=["mon", "wed", "sat"],
)
def test_decision_is_noon_london_in_winter_too(match_date: date, decided: datetime) -> None:
    assert decision_at(match_date, None) == decided


@pytest.mark.parametrize(
    ("match_date", "decided"),
    [
        (date(2024, 3, 31), _utc(2024, 3, 29, 12)),  # yaz saatine geçilen pazar; karar günü kışta
        (date(2024, 4, 1), _utc(2024, 3, 29, 12)),  # maç günü yazda, karar günü kışta
        (date(2024, 10, 28), _utc(2024, 10, 25, 11)),  # maç günü kışta, karar günü yazda
    ],
    ids=["spring-sunday", "spring-monday", "autumn-monday"],
)
def test_the_offset_comes_from_the_decision_day_across_a_clock_change(
    match_date: date, decided: datetime
) -> None:
    assert decision_at(match_date, None) == decided


@pytest.mark.parametrize(
    ("kickoff", "decided"),
    [
        (_utc(2024, 8, 9, 10, 30), None),  # cuma 11:30 BST: kararın önünde
        (_utc(2024, 8, 9, 11), None),  # tam 12:00 BST: eşitlikte karar yok
        (_utc(2024, 8, 9, 11, 1), _utc(2024, 8, 9, 11)),  # 12:01 BST
        (_utc(2024, 8, 9, 18, 45), _utc(2024, 8, 9, 11)),
    ],
    ids=["before", "equal", "one-minute-after", "evening"],
)
def test_a_friday_match_has_a_decision_only_when_it_kicks_off_after_noon(
    kickoff: datetime, decided: datetime | None
) -> None:
    assert decision_at(date(2024, 8, 9), kickoff) == decided


def test_a_tuesday_noon_kickoff_in_winter_has_no_decision() -> None:
    assert decision_at(date(2024, 1, 16), _utc(2024, 1, 16, 12)) is None
    assert decision_at(date(2024, 1, 16), _utc(2024, 1, 16, 12, 1)) == _utc(2024, 1, 16, 12)


def test_without_a_kickoff_every_day_of_a_year_decides_on_the_last_tuesday_or_friday() -> None:
    for offset in range(366):
        day = date(2024, 1, 1) + timedelta(days=offset)
        decided = decision_at(day, None)
        assert decided is not None, day
        local = decided.astimezone(LONDON)
        assert (local.hour, local.minute) == (DECISION_HOUR, 0), day
        assert local.weekday() == (1 if day.weekday() in (1, 2, 3) else 4), day
        assert timedelta(0) <= day - local.date() <= timedelta(days=3), day


def test_a_result_is_known_three_hours_after_a_known_kickoff() -> None:
    assert result_known_at(date(2024, 8, 10), _utc(2024, 8, 10, 14)) == _utc(2024, 8, 10, 17)


@pytest.mark.parametrize(
    ("match_date", "known"),
    [
        (date(2024, 1, 20), _utc(2024, 1, 21, 3)),  # kış
        (date(2024, 8, 10), _utc(2024, 8, 11, 2)),  # yaz
        (date(2024, 3, 30), _utc(2024, 3, 31, 2)),  # ertesi gün yaz saatine geçiliyor
        (date(2024, 10, 26), _utc(2024, 10, 27, 3)),  # ertesi gün kışa dönülüyor
    ],
    ids=["winter", "summer", "spring-forward", "fall-back"],
)
def test_without_a_kickoff_the_result_is_known_next_day_at_three_london(
    match_date: date, known: datetime
) -> None:
    assert result_known_at(match_date, None) == known


def test_both_instants_come_back_in_utc() -> None:
    decided = decision_at(date(2024, 8, 10), None)
    london_kickoff = datetime(2024, 8, 10, 15, tzinfo=LONDON)
    instants = (
        decided,
        result_known_at(date(2024, 8, 10), None),
        result_known_at(date(2024, 8, 10), london_kickoff),
    )
    assert all(instant is not None and instant.tzinfo is UTC for instant in instants)
    assert instants[2] == _utc(2024, 8, 10, 17)


@pytest.mark.parametrize("function", [decision_at, result_known_at], ids=["decision", "result"])
def test_a_naive_kickoff_is_refused(function: Callable[[date, datetime | None], object]) -> None:
    with pytest.raises(ValueError, match="saat dilimsiz"):
        function(date(2024, 8, 10), datetime(2024, 8, 10, 14))


def test_every_decision_precedes_its_kickoff_and_every_result_follows_it() -> None:
    start = _utc(2024, 3, 25, 0)  # yaz saati geçişini kapsayan iki hafta
    for hours in range(0, 24 * 14, 5):
        kickoff = start + timedelta(hours=hours)
        match_date = kickoff.astimezone(LONDON).date()
        decided = decision_at(match_date, kickoff)
        assert decided is None or decided < kickoff, kickoff
        assert result_known_at(match_date, kickoff) > kickoff, kickoff
