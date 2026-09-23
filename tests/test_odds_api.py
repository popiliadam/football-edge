from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from football_edge.odds_api import (
    Quota,
    QuotaExhausted,
    fetch_event_times,
    fetch_odds,
    flatten_odds,
    guard_quota,
    read_quota,
)

PAYLOAD = [
    {
        "id": "abc123",
        "sport_key": "soccer_epl",
        "sport_title": "EPL",
        "commence_time": "2026-09-20T14:00:00Z",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": "2026-09-19T10:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.95},
                            {"name": "Chelsea", "price": 4.10},
                            {"name": "Draw", "price": 3.60},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.90, "point": 2.5},
                            {"name": "Under", "price": 1.95, "point": 2.5},
                        ],
                    },
                ],
            }
        ],
    }
]


def test_flatten_produces_one_row_per_outcome() -> None:
    rows = flatten_odds(PAYLOAD)
    assert len(rows) == 5


def test_flatten_carries_event_and_market_fields() -> None:
    rows = flatten_odds(PAYLOAD)
    first = rows[0]
    assert first.event_id == "abc123"
    assert first.home_team == "Arsenal"
    assert first.bookmaker == "pinnacle"
    assert first.market == "h2h"
    assert first.outcome == "Arsenal"
    assert first.price == 1.95
    assert first.point is None


def test_flatten_keeps_totals_point() -> None:
    rows = flatten_odds(PAYLOAD)
    over = next(r for r in rows if r.outcome == "Over")
    assert over.point == 2.5
    assert over.market == "totals"


def test_flatten_handles_event_with_no_bookmakers() -> None:
    assert flatten_odds([{**PAYLOAD[0], "bookmakers": []}]) == ()


def test_read_quota_parses_headers() -> None:
    quota = read_quota(
        {"x-requests-remaining": "487", "x-requests-used": "13", "x-requests-last": "1"}
    )
    assert quota == Quota(remaining=487, used=13, last_cost=1)


def test_guard_quota_raises_below_threshold() -> None:
    with pytest.raises(QuotaExhausted, match="kalan kredi"):
        guard_quota(Quota(remaining=5, used=495, last_cost=1), min_remaining=10)


def test_guard_quota_passes_above_threshold() -> None:
    guard_quota(Quota(remaining=50, used=450, last_cost=1), min_remaining=10)


def test_fetch_odds_builds_request_and_returns_rows() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json=PAYLOAD,
            headers={
                "x-requests-remaining": "499",
                "x-requests-used": "1",
                "x-requests-last": "1",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rows, quota = fetch_odds(client, "KEY", "soccer_epl", commence_time_to="2026-09-26T00:00:00Z")

    assert len(rows) == 5
    assert quota.remaining == 499

    parsed = urlparse(str(captured["url"]))
    assert parsed.path == "/v4/sports/soccer_epl/odds"
    # Ham dizede yüzde-kodlamaya bakma: onu httpx belirler, biz değil.
    params = parse_qs(parsed.query)
    assert params["apiKey"] == ["KEY"]
    assert params["regions"] == ["eu"]
    assert params["markets"] == ["h2h"]
    assert params["oddsFormat"] == ["decimal"]
    assert params["dateFormat"] == ["iso"]
    assert params["commenceTimeTo"] == ["2026-09-26T00:00:00Z"]


def test_fetch_odds_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "invalid key"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_odds(client, "BAD", "soccer_epl")


# ── Boş tur bekçisi: ücretsiz `/events` ucu ─────────────────────────────────
# `/odds` milli arada da, sessiz bir arızada da (anahtar adı değişti, bölge değişti) AYNI boş
# listeyi döner. Ufukta fikstür olup olmadığını ücretsiz `/events` söyler (ölçüldü:
# `x-requests-last: 0`); ikisini ayıran tek soru bu.

EVENTS_PAYLOAD = [
    {
        "id": "abc123",
        "sport_key": "soccer_epl",
        "sport_title": "EPL",
        "commence_time": "2026-10-09T18:45:00Z",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
    },
    {
        "id": "def456",
        "sport_key": "soccer_epl",
        "sport_title": "EPL",
        "commence_time": "2026-10-10T14:00:00Z",
        "home_team": "Leeds",
        "away_team": "Fulham",
    },
]


def test_fetch_event_times_asks_the_free_events_endpoint_with_the_same_horizon() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json=EVENTS_PAYLOAD,
            headers={
                "x-requests-remaining": "499",
                "x-requests-used": "1",
                "x-requests-last": "0",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    times = fetch_event_times(client, "KEY", "soccer_epl", commence_time_to="2026-09-30T06:22:00Z")

    assert times == ("2026-10-09T18:45:00Z", "2026-10-10T14:00:00Z")
    parsed = urlparse(str(captured["url"]))
    assert parsed.path == "/v4/sports/soccer_epl/events"
    params = parse_qs(parsed.query)
    assert params["apiKey"] == ["KEY"]
    assert params["commenceTimeTo"] == ["2026-09-30T06:22:00Z"]
    assert params["dateFormat"] == ["iso"]
    # `/events` bölge ve piyasa almaz: ikisi `/odds`un kredi çarpanıdır, burada yeri yok.
    assert "regions" not in params and "markets" not in params


def test_fetch_event_times_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "down"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_event_times(client, "KEY", "soccer_epl", commence_time_to="2026-09-30T06:22:00Z")
