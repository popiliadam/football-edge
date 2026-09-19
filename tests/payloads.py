"""The Odds API yanıtları için test kurgusu (çevrimdışı)."""

from __future__ import annotations

from typing import Any

QUOTA_HEADERS = {
    "x-requests-remaining": "400",
    "x-requests-used": "100",
    "x-requests-last": "1",
}


def quota_headers(remaining: int) -> dict[str, str]:
    return {**QUOTA_HEADERS, "x-requests-remaining": str(remaining)}


def event(
    event_id: str,
    commence_time: str,
    *,
    sport_key: str = "soccer_good",
    prices: tuple[float, ...] = (1.90, 4.00),
) -> dict[str, Any]:
    return {
        "id": event_id,
        "sport_key": sport_key,
        "commence_time": commence_time,
        "home_team": "A",
        "away_team": "B",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": "2026-09-19T10:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": f"O{index}", "price": price}
                            for index, price in enumerate(prices)
                        ],
                    }
                ],
            }
        ],
    }
