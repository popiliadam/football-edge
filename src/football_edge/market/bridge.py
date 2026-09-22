"""Tarihsel ↔ canlı kapanış köprüsü: kendi mühürlediğimiz kapanış ile football-data'nın `AvgC`'si.

Aynı maç `(lig, İngiltere tarihi, ev, deplasman)` ile eşlenir; iki taraf aynı yöntemle vig'den
arındırılıp sonuç başına karşılaştırılır (tasarım §9). Eşlenemeyen canlı maç düşürülmez, sayılır.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import psycopg
import yaml

from football_edge.backtest.timeline import LONDON
from football_edge.history.holdout import POST, select_periods
from football_edge.history.types import CLOSING, H2H, HistMatch
from football_edge.market.devig import InvalidPrices, devig, match_probs
from football_edge.market.metrics import Interval, bootstrap_mean
from football_edge.naming import normalise_team

LOGGER = logging.getLogger("football_edge.market.bridge")

# The Odds API'nin 1X2 market anahtarı ve beraberlik sonucunun adı: mühür turu
# (`rounds.run_seal` → `odds_api.fetch_odds(markets="h2h")`) satırları bu adlarla yazar.
LIVE_MARKET = "h2h"
LIVE_DRAW = "Draw"
REFERENCE_BOOK = "Avg"  # (Avg, CLOSING) = football-data'nın AvgC'si — referans kapanış (D3)

_CLOSINGS = """
    SELECT m.id, m.league_id, m.commence_time, m.home_team, m.away_team,
           s.bookmaker, s.outcome, s.price, s.observed_at
    FROM matches m
    JOIN odds_snapshots s ON s.match_id = m.id
    WHERE s.is_closing AND s.market = %s AND m.commence_time >= %s
    ORDER BY m.commence_time, m.id
"""

_OUTCOMES = ("H", "D", "A")
Books = Mapping[str, Mapping[str, float]]  # kitap → {sonuç adı: fiyat}
Key = tuple[str, date, str, str]


@dataclass(frozen=True)
class LiveClosing:
    match_id: str
    league_id: str
    kickoff: datetime
    home: str
    away: str
    prices: tuple[float, float, float]  # kitapların kapanış fiyatlarının aritmetik ortalaması
    books: int


@dataclass(frozen=True)
class Pairing:
    pairs: tuple[tuple[LiveClosing, HistMatch], ...]
    unmatched_live: tuple[LiveClosing, ...]


@dataclass(frozen=True)
class BridgeReport:
    n: int
    method: str
    mean_diff: tuple[Interval, Interval, Interval]  # p_bizim − p_AvgC (H, D, A)
    rms: float
    unmatched: int  # karşılaştırılamayan canlı maç: eşlenemeyen + AvgC'si eksik/çözülemeyen


def load_aliases(path: Path) -> Mapping[str, str]:
    """The Odds API takım adı → football-data takım adı."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("aliases"), dict):
        raise ValueError(f"{path}: kökte 'aliases' eşlemesi yok")
    aliases: dict[Any, Any] = raw["aliases"]
    for name, target in aliases.items():
        if not isinstance(name, str) or not isinstance(target, str) or not target:
            raise ValueError(f"{path}: takma ad metinden metne olmalı: {name!r} → {target!r}")
    return MappingProxyType(dict(aliases))


def _grouped(records: Sequence[tuple[Any, ...]]) -> dict[str, dict[str, dict[str, float]]]:
    """maç → kitap → sonuç → fiyat; aynı kitap-sonuç birden çok turda yazıldıysa SON gözlem."""
    grouped: dict[str, dict[str, dict[str, float]]] = {}
    for record in sorted(records, key=lambda row: row[8]):  # observed_at: artan
        match_id, book, outcome = str(record[0]), str(record[5]), str(record[6])
        grouped.setdefault(match_id, {}).setdefault(book, {})[outcome] = float(record[7])
    return grouped


def _consensus(books: Books, home: str, away: str) -> tuple[tuple[float, float, float], int] | None:
    """Üç sonucu da taşıyan kitapların sonuç başına ortalama fiyatı ve kitap sayısı."""
    names = (home, LIVE_DRAW, away)
    full = [book for book in books.values() if all(name in book for name in names)]
    if not full:
        return None
    count = len(full)
    home_price, draw_price, away_price = (
        math.fsum(book[name] for book in full) / count for name in names
    )
    return (home_price, draw_price, away_price), count


def load_live_closings(
    conn: psycopg.Connection[Any], *, since: datetime
) -> tuple[LiveClosing, ...]:
    """`since`ten sonra başlayan maçların mühürlü 1X2 kapanışları, kitaplar üzerinden ortalama."""
    with conn.cursor() as cur:
        cur.execute(_CLOSINGS, (LIVE_MARKET, since))
        records = cur.fetchall()
    heads = {str(row[0]): (str(row[1]), row[2], str(row[3]), str(row[4])) for row in records}
    grouped = _grouped(records)
    found: list[LiveClosing] = []
    for match_id, (league_id, kickoff, home, away) in heads.items():
        consensus = _consensus(grouped[match_id], home, away)
        if consensus is None:
            LOGGER.warning("maç=%s kapanışında üç sonucu tam kitap yok — köprüye girmedi", match_id)
            continue
        prices, books = consensus
        found.append(LiveClosing(match_id, league_id, kickoff, home, away, prices, books))
    return tuple(sorted(found, key=lambda closing: (closing.kickoff, closing.match_id)))


def _key(closing: LiveClosing, aliases: Mapping[str, str], codes: Mapping[str, str]) -> Key | None:
    code = codes.get(closing.league_id)
    if code is None:
        return None
    return (
        code,
        closing.kickoff.astimezone(LONDON).date(),  # football-data'nın Date'i İngiltere tarihidir
        normalise_team(aliases.get(closing.home, closing.home)),
        normalise_team(aliases.get(closing.away, closing.away)),
    )


def pair(
    live: Sequence[LiveClosing],
    hist: Sequence[HistMatch],
    *,
    aliases: Mapping[str, str],
    codes_by_league_id: Mapping[str, str],
) -> Pairing:
    # Köprü yalnız "sonrası" dönemine bakar: holdout anahtarsız okunmaz ve burada istenmez.
    index = {
        (match.league, match.date, normalise_team(match.home), normalise_team(match.away)): match
        for match in select_periods(hist, periods=frozenset({POST}))
    }
    pairs: list[tuple[LiveClosing, HistMatch]] = []
    unmatched: list[LiveClosing] = []
    for closing in live:
        key = _key(closing, aliases, codes_by_league_id)
        found = None if key is None else index.get(key)
        if found is None:
            unmatched.append(closing)
        else:
            pairs.append((closing, found))
    return Pairing(pairs=tuple(pairs), unmatched_live=tuple(unmatched))


def _live_probs(closing: LiveClosing, method: str) -> tuple[float, ...] | None:
    try:
        return devig(closing.prices, method)
    except InvalidPrices:
        return None


def compare(pairing: Pairing, *, method: str) -> BridgeReport:
    """Sonuç başına p_bizim − p_AvgC (ikisi de `method` ile); ortalama aralığı ve RMS."""
    diffs: list[tuple[float, ...]] = []
    skipped = 0
    for closing, match in pairing.pairs:
        theirs = match_probs(match, book=REFERENCE_BOOK, market=H2H, phase=CLOSING, method=method)
        ours = _live_probs(closing, method)
        if theirs is None or ours is None:
            skipped += 1
            continue
        diffs.append(tuple(mine - reference for mine, reference in zip(ours, theirs, strict=True)))
    if not diffs:
        raise ValueError(
            "karşılaştırılabilir eşleşme yok: "
            f"eşlenemeyen {len(pairing.unmatched_live)}, AvgC'si eksik/çözülemeyen {skipped}"
        )
    flat = [value for row in diffs for value in row]
    home, draw, away = (bootstrap_mean([row[index] for row in diffs]) for index in range(3))
    return BridgeReport(
        n=len(diffs),
        method=method,
        mean_diff=(home, draw, away),
        rms=math.sqrt(math.fsum(value * value for value in flat) / len(flat)),
        unmatched=len(pairing.unmatched_live) + skipped,
    )


def render_bridge_report(report: BridgeReport, *, generated_at: datetime, since: date) -> str:
    """Markdown rapor: yalnız toplu sayılar; maç, takım, maç tarihi satırı YOK (spec §3.2/4)."""
    rows = [
        f"| {name} | {interval.estimate:+.4f} | [{interval.low:+.4f}, {interval.high:+.4f}] |"
        for name, interval in zip(_OUTCOMES, report.mean_diff, strict=True)
    ]
    lines = [
        "# Tarihsel ↔ canlı kapanış köprüsü",
        "",
        f"Üretildi: {generated_at.isoformat()} · Canlı mühürler: {since.isoformat()} ve sonrasında "
        f"başlayan maçlar · Yöntem: {report.method} (iki tarafta da)",
        "",
        f"Karşılaştırılan maç (N): {report.n} · Karşılaştırılamayan canlı maç: {report.unmatched} "
        "(eşlenemeyen ya da AvgC'si eksik/çözülemeyen)",
        "",
        "| Sonuç | Ortalama fark (bizim − AvgC) | %95 aralık |",
        "|---|---|---|",
        *rows,
        "",
        f"RMS (bütün sonuç farkları): {report.rms:.4f}",
        "",
        f"Aralık N küçükken geniştir (N = {report.n}): rapor her hafta yeniden üretilir, canlı "
        "altı lig haftada ~60 maç ekler (tasarım §9, §13/13). Anlamlı bir sistematik fark doğrusal "
        "bir düzeltme ÖNERİSİ doğurur, uygulanmaz.",
    ]
    return "\n".join(lines) + "\n"
