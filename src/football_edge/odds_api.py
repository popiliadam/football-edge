from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

BASE_URL = "https://api.the-odds-api.com/v4"


class QuotaExhausted(RuntimeError):
    """Kalan kredi güvenli eşiğin altına indi."""


@dataclass(frozen=True)
class Quota:
    remaining: int
    used: int
    last_cost: int


@dataclass(frozen=True)
class PriceRow:
    event_id: str
    sport_key: str
    commence_time: str
    home_team: str
    away_team: str
    bookmaker: str
    bookmaker_last_update: str
    market: str
    outcome: str
    point: float | None
    price: float


def _rows_for_event(event: dict[str, Any]) -> tuple[PriceRow, ...]:
    rows: tuple[PriceRow, ...] = ()
    for bookmaker in event.get("bookmakers", ()):
        for market in bookmaker.get("markets", ()):
            for outcome in market.get("outcomes", ()):
                point = outcome.get("point")
                rows = (
                    *rows,
                    PriceRow(
                        event_id=event["id"],
                        sport_key=event["sport_key"],
                        commence_time=event["commence_time"],
                        home_team=event["home_team"],
                        away_team=event["away_team"],
                        bookmaker=bookmaker["key"],
                        bookmaker_last_update=bookmaker["last_update"],
                        market=market["key"],
                        outcome=outcome["name"],
                        point=None if point is None else float(point),
                        price=float(outcome["price"]),
                    ),
                )
    return rows


def flatten_odds(payload: list[dict[str, Any]]) -> tuple[PriceRow, ...]:
    rows: tuple[PriceRow, ...] = ()
    for event in payload:
        rows = (*rows, *_rows_for_event(event))
    return rows


def read_quota(headers: Mapping[str, str]) -> Quota:
    return Quota(
        remaining=int(headers["x-requests-remaining"]),
        used=int(headers["x-requests-used"]),
        last_cost=int(headers["x-requests-last"]),
    )


def guard_quota(quota: Quota, min_remaining: int) -> None:
    if quota.remaining < min_remaining:
        raise QuotaExhausted(f"kalan kredi {quota.remaining} < eşik {min_remaining}")


def fetch_odds(
    client: httpx.Client,
    api_key: str,
    sport_key: str,
    *,
    regions: str = "eu",
    markets: str = "h2h",
    commence_time_to: str | None = None,
) -> tuple[tuple[PriceRow, ...], Quota]:
    params: dict[str, str] = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    if commence_time_to is not None:
        params["commenceTimeTo"] = commence_time_to

    response = client.get(f"{BASE_URL}/sports/{sport_key}/odds", params=params, timeout=30.0)
    response.raise_for_status()
    return flatten_odds(response.json()), read_quota(response.headers)
