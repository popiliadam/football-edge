"""Karar anı filtresi (spec §5/1) ve özellik vektörü (spec §6).

Sınır testleri mutasyona duyarlıdır: `available_at < decided_at` ya da `asked_at < decided_at`
`<=`e çevrilirse "tam eşit an" testleri kırmızı verir (spec §10).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from football_edge.features.derive import (
    FeatureVector,
    SideAnswer,
    features_of,
    item_set_hash,
    select_items,
)
from football_edge.features.types import HOME, OBSERVED, ItemGate, StoredNews

DECIDED = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
TICK = timedelta(microseconds=1)
MATCH = "m1"


def news(item_id: int, available_at: datetime, *, content: str | None = None) -> StoredNews:
    return StoredNews(
        item_id=item_id,
        source_id="ajansspor",
        lang="tr",
        title=f"haber {item_id}",
        body=None,
        url=f"https://ajansspor.com/haber/{item_id}",
        published_at_claimed=available_at,
        available_at=available_at,
        availability_basis=OBSERVED,
        content_hash=content or f"h{item_id}",
    )


def gate(
    item_id: int,
    *,
    asked_at: datetime = DECIDED - timedelta(hours=1),
    match_id: str | None = MATCH,
    belongs: float = 0.9,
    reliability: float = 0.9,
    cluster_id: str | None = None,
) -> ItemGate:
    return ItemGate(
        item_id=item_id,
        match_id=match_id,
        side=HOME,
        belongs=belongs,
        reliability=reliability,
        cluster_id=cluster_id or str(item_id),
        asked_at=asked_at,
    )


def select(
    items: list[StoredNews], gates: list[ItemGate], *, live: bool = True
) -> tuple[StoredNews, ...]:
    return select_items(
        items,
        {entry.item_id: entry for entry in gates},
        match_id=MATCH,
        decided_at=DECIDED,
        live=live,
        min_belongs=0.5,
        min_reliability=0.5,
    )


@pytest.mark.leakage
def test_news_available_exactly_at_the_decision_is_outside() -> None:
    assert select([news(1, DECIDED)], [gate(1)]) == ()


@pytest.mark.leakage
def test_news_available_a_microsecond_before_the_decision_is_inside() -> None:
    item = news(1, DECIDED - TICK)

    assert select([item], [gate(1)]) == (item,)


@pytest.mark.leakage
def test_live_tier1_answer_given_exactly_at_the_decision_is_outside() -> None:
    item = news(1, DECIDED - timedelta(hours=2))

    assert select([item], [gate(1, asked_at=DECIDED)]) == ()
    assert select([item], [gate(1, asked_at=DECIDED - TICK)]) == (item,)


@pytest.mark.leakage
def test_archive_ignores_when_tier1_was_asked_but_not_availability() -> None:
    """Arşivde kademe 1 sonradan sorulur (geri doldurma); koruma `available_at`in payıdır."""
    early = news(1, DECIDED - timedelta(hours=2))
    late = news(2, DECIDED)
    backfilled = DECIDED + timedelta(days=300)

    chosen = select(
        [early, late], [gate(1, asked_at=backfilled), gate(2, asked_at=backfilled)], live=False
    )

    assert chosen == (early,)


@pytest.mark.leakage
def test_a_cluster_is_represented_by_its_earliest_usable_item() -> None:
    first = news(1, DECIDED - timedelta(hours=5))
    repeat = news(2, DECIDED - timedelta(hours=1))
    after = news(3, DECIDED + timedelta(hours=1))
    gates = [gate(n, cluster_id="k") for n in (1, 2, 3)]

    assert select([after, repeat, first], gates) == (first,)
    assert select([after, repeat], gates[1:]) == (repeat,)


@pytest.mark.leakage
def test_a_repeat_after_the_decision_cannot_stand_in_for_an_unusable_original() -> None:
    """Küme temsilcisi süzgeçten SONRA seçilir: kararla aynı anda gelen tekrar içeri sızamaz."""
    original = news(1, DECIDED - timedelta(hours=3))
    repeat = news(2, DECIDED)
    gates = [gate(1, cluster_id="k", asked_at=DECIDED + TICK), gate(2, cluster_id="k")]

    assert select([original, repeat], gates) == ()


def test_news_of_another_match_or_without_a_gate_is_outside() -> None:
    mine, other, ungated = (news(n, DECIDED - timedelta(hours=n)) for n in (1, 2, 3))

    chosen = select([mine, other, ungated], [gate(1), gate(2, match_id="m2")])

    assert chosen == (mine,)


def test_unstored_news_is_outside() -> None:
    unstored = StoredNews(None, "s", "tr", "t", None, "u", None, DECIDED - TICK, OBSERVED, "h")

    assert select([unstored], []) == ()


def test_belongs_and_reliability_thresholds_are_inclusive() -> None:
    at_threshold = news(1, DECIDED - timedelta(hours=1))
    weak = news(2, DECIDED - timedelta(hours=2))
    doubtful = news(3, DECIDED - timedelta(hours=3))
    gates = [
        gate(1, belongs=0.5, reliability=0.5),
        gate(2, belongs=0.49),
        gate(3, reliability=0.49),
    ]

    assert select([at_threshold, weak, doubtful], gates) == (at_threshold,)


def test_selection_is_ordered_by_availability() -> None:
    late, early = news(1, DECIDED - timedelta(hours=1)), news(2, DECIDED - timedelta(hours=9))

    assert select([late, early], [gate(1), gate(2)]) == (early, late)


@pytest.mark.leakage
def test_a_naive_decision_time_is_refused() -> None:
    with pytest.raises(ValueError, match="saat dilimsiz"):
        select_items(
            [],
            {},
            match_id=MATCH,
            decided_at=DECIDED.replace(tzinfo=None),
            live=True,
            min_belongs=0.5,
            min_reliability=0.5,
        )


def test_item_set_hash_ignores_order_and_follows_content() -> None:
    a, b = news(1, DECIDED, content="a"), news(2, DECIDED, content="b")

    assert item_set_hash([a, b]) == item_set_hash([b, a])
    assert item_set_hash([a, b]) != item_set_hash([a])
    assert item_set_hash([a]) != item_set_hash([news(1, DECIDED, content="a2")])
    assert len(item_set_hash([])) == 64


def test_feature_is_home_minus_away() -> None:
    vector = features_of({"x": SideAnswer(0.8, 0.3, 0.9)}, ["x"], c_min=0.5)

    assert vector.names == ("x",)
    assert vector.values == (pytest.approx(0.5),)
    assert vector.missing == 0


def test_missing_or_one_sided_answers_are_zero_and_counted() -> None:
    answers = {"one_sided": SideAnswer(0.8, None, 0.9), "full": SideAnswer(0.2, 0.6, 0.9)}

    vector = features_of(answers, ["absent", "one_sided", "full"], c_min=0.5)

    assert vector.names == ("absent", "one_sided", "full")
    assert vector.values[:2] == (0.0, 0.0)
    assert vector.values[2] == pytest.approx(-0.4)
    assert vector.missing == 2


def test_low_confidence_is_zeroed_and_the_threshold_is_inclusive() -> None:
    answers = {"low": SideAnswer(0.9, 0.1, 0.49), "edge": SideAnswer(0.9, 0.1, 0.5)}

    vector = features_of(answers, ["low", "edge"], c_min=0.5)

    assert vector.values == (0.0, pytest.approx(0.8))
    assert vector.missing == 1


def test_duplicate_feature_names_are_refused() -> None:
    with pytest.raises(ValueError, match="tekil"):
        features_of({}, ["x", "x"], c_min=0.5)


def test_no_answer_at_all_gives_a_zero_vector() -> None:
    vector = features_of({}, ["a", "b"], c_min=0.5)

    assert vector == FeatureVector(("a", "b"), (0.0, 0.0), 2)
    assert all(math.isfinite(value) for value in vector.values)


# ── Review Focus: sonlu olmayan cevap kaydırmaya sızmamalı ────────────────────────────────────


@pytest.mark.parametrize(
    "answer",
    [
        SideAnswer(math.nan, 0.2, 0.9),
        SideAnswer(0.7, math.inf, 0.9),
        SideAnswer(0.7, 0.2, math.nan),
    ],
)
def test_a_non_finite_answer_is_missing_not_a_nan_feature(answer: SideAnswer) -> None:
    """NaN'lı güven `confidence < c_min` sınamasını False'la geçerdi; özellik NaN olurdu."""
    vector = features_of({"x": answer}, ["x"], c_min=0.5)

    assert vector.values == (0.0,)
    assert vector.missing == 1
