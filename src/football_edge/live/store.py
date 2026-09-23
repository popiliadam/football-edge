"""Defterden canlı kurucunun okuduğu satırlar (salt okuma). Yazan yol yok."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg

from football_edge.live.context import LIVE_H2H, LiveMatch, Quote

_MATCHES = """
    SELECT id, league_id, commence_time, home_team, away_team
    FROM matches
    WHERE commence_time >= %s AND commence_time < %s
    ORDER BY commence_time, id
"""
_QUOTES = """
    SELECT match_id, observed_at, bookmaker, market, outcome, price
    FROM odds_snapshots
    WHERE match_id = ANY(%s) AND market = %s AND observed_at <= %s
    ORDER BY match_id, observed_at, bookmaker, outcome
"""


def load_live_matches(
    conn: psycopg.Connection[Any], *, since: datetime, until: datetime
) -> tuple[LiveMatch, ...]:
    with conn.cursor() as cur:
        cur.execute(_MATCHES, (since, until))
        rows = cur.fetchall()
    return tuple(
        LiveMatch(str(row[0]), str(row[1]), row[2], str(row[3]), str(row[4])) for row in rows
    )


def load_quotes(
    conn: psycopg.Connection[Any], match_ids: tuple[str, ...], *, until: datetime
) -> tuple[Quote, ...]:
    """`until`e kadar gözlenen 1X2 satırları; fiyat `numeric` → float."""
    if not match_ids:
        return ()
    with conn.cursor() as cur:
        cur.execute(_QUOTES, (list(match_ids), LIVE_H2H, until))
        rows = cur.fetchall()
    return tuple(
        Quote(str(row[0]), row[1], str(row[2]), str(row[3]), str(row[4]), float(row[5]))
        for row in rows
    )
