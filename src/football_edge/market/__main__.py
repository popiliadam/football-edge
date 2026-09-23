"""Piyasa CLI'ı: `efficiency` (tasarım §8) ve `bridge` (tasarım §9) raporları.

`efficiency`de kilit HER ölçümden önce doğrulanır (`load_matches(..., lock=lock)`, R96): kilit
dosyası bozuksa ya da satırlar kilitli özetlere uymuyorsa tek bir ölçüt hesaplanmaz, rapor yazılmaz.
`bridge` yalnız kilitsiz "sonrası" dönemine bakar (`load_matches` DEV + POST, `pair` POST süzer).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time
from pathlib import Path
from types import MappingProxyType

from football_edge.collect import EXIT_SOURCE_FAILED, configure_logging
from football_edge.collector import ContractViolation
from football_edge.db import connect
from football_edge.history.catalog import Catalog, HistoryLeague, load_catalog
from football_edge.history.holdout import HOLDOUT_END
from football_edge.history.lock import EXIT_LOCK_VIOLATION, LockViolation, load_lock
from football_edge.history.sync import load_matches
from football_edge.history.types import HistMatch
from football_edge.market.bridge import (
    compare,
    load_aliases,
    load_live_closings,
    pair,
    render_bridge_report,
)
from football_edge.market.devig import DEFAULT_METHOD, METHODS
from football_edge.market.efficiency import (
    RESAMPLES,
    LeagueEfficiency,
    Unmeasurable,
    best_method,
    candidates,
    league_efficiency,
    method_scores,
    rank,
    render_report,
)

LOGGER = logging.getLogger("football_edge.market")
LOCK_PATH = Path("config/history_lock.yaml")
CATALOG_PATH = Path("config/history_leagues.yaml")
ALIASES_PATH = Path("config/history_aliases.yaml")
# Kilitli dönemin bir satırı değişti ya da kayboldu: `history` CLI'ıyla aynı kod; `collect`in 2–8'i
# ve 0/1 dışında.
# Köprü: karşılaştırılabilir tek eşleşme yok (N = 0 → aralık tanımsız). Rapor yazılmaz; çoğu kez
# takma ad eksiktir (Task 8 Step 12).
EXIT_NO_PAIRS = 10


def _resamples(text: str) -> int:
    """`--resamples` ≥ 1: 0 her ligi "ölçülemedi" yapıp aday listesini boşaltırdı (R115)."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"tekrar sayısı ≥ 1 olmalı: {value}")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.market")
    commands = parser.add_subparsers(dest="command", required=True)
    efficiency = commands.add_parser("efficiency", help="piyasa verimliliği raporu (geliştirme)")
    efficiency.add_argument("--out", type=Path, required=True, help="yazılacak markdown rapor")
    efficiency.add_argument("--lock", type=Path, default=LOCK_PATH)
    efficiency.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    efficiency.add_argument("--resamples", type=_resamples, default=RESAMPLES)
    bridge = commands.add_parser("bridge", help="tarihsel ↔ canlı kapanış köprüsü raporu")
    bridge.add_argument("--out", type=Path, required=True, help="yazılacak markdown rapor")
    bridge.add_argument(
        "--since",
        type=date.fromisoformat,
        default=HOLDOUT_END,
        help="bu tarihten (UTC gece yarısı) sonra başlayan canlı maçlar; varsayılan: sonrası",
    )
    bridge.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    bridge.add_argument("--aliases", type=Path, default=ALIASES_PATH)
    bridge.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD)
    return parser


def _measure(
    catalog: Catalog,
    matches_by_league: Mapping[str, tuple[HistMatch, ...]],
    *,
    method: str,
    resamples: int,
) -> tuple[tuple[LeagueEfficiency, ...], tuple[HistoryLeague, ...], Mapping[str, int]]:
    """Ölçülen satırlar, ölçülemeyen ligler ve N'leri; biri raporu düşürmez (adıyla anılır)."""
    rows: list[LeagueEfficiency] = []
    unmeasured: list[HistoryLeague] = []
    counts: dict[str, int] = {}
    for league in catalog.leagues:
        try:
            rows.append(
                league_efficiency(
                    league,
                    matches_by_league.get(league.code, ()),
                    method=method,
                    resamples=resamples,
                )
            )
        except Unmeasurable as missing:
            LOGGER.warning("lig=%s ölçülemedi (N=%d) — %s", league.code, missing.n, missing)
            unmeasured.append(league)
            counts[league.code] = missing.n
    return tuple(rows), tuple(unmeasured), MappingProxyType(counts)


def _efficiency(args: argparse.Namespace, now: datetime) -> int:
    catalog = load_catalog(args.catalog)
    try:
        lock = load_lock(args.lock)
        with connect() as conn:
            matches_by_league = load_matches(conn, catalog, lock=lock)
    except LockViolation as violation:
        LOGGER.error("kilit doğrulanamadı — hiçbir ölçüt hesaplanmadı: %s", violation)
        return EXIT_LOCK_VIOLATION
    except ContractViolation as violation:
        # Eksik ya da sözleşmeyi geçmeyen önbellekle ölçülmez (history CLI'ıyla aynı kod).
        LOGGER.error("önbellek kullanılamaz — rapor üretilmedi: %s", violation)
        return EXIT_SOURCE_FAILED
    pooled = [match for matches in matches_by_league.values() for match in matches]
    scores = method_scores(pooled)
    method = best_method(scores)
    rows, unmeasured, counts = _measure(
        catalog, matches_by_league, method=method, resamples=args.resamples
    )
    ranking = rank(rows)
    chosen = candidates(rows, ranking, lock=lock, leagues=catalog.leagues)
    report = render_report(
        rows,
        ranking,
        scores=scores,
        candidates=chosen,
        generated_at=now,
        unmeasured=unmeasured,
        unmeasured_counts=counts,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    LOGGER.info(
        "verimlilik: %d lig · yöntem=%s · aday=%s · ölçülemeyen=%s · rapor=%s",
        len(rows),
        method,
        ",".join(chosen) or "yok",
        ",".join(league.code for league in unmeasured) or "yok",
        args.out,
    )
    return 0


def _bridge(args: argparse.Namespace, now: datetime) -> int:
    catalog = load_catalog(args.catalog)
    aliases = load_aliases(args.aliases)
    since = datetime.combine(args.since, time.min, tzinfo=UTC)
    try:
        with connect() as conn:
            matches_by_league = load_matches(conn, catalog)
            live = load_live_closings(conn, since=since)
    except ContractViolation as violation:
        LOGGER.error("önbellek kullanılamaz — köprü raporu üretilmedi: %s", violation)
        return EXIT_SOURCE_FAILED
    codes = {league.league_id: league.code for league in catalog.leagues}
    hist = [match for matches in matches_by_league.values() for match in matches]
    pairing = pair(live, hist, aliases=aliases, codes_by_league_id=codes)
    try:
        report = compare(pairing, method=args.method)
    except ValueError as empty:
        LOGGER.error("köprü: %s — %d canlı kapanış, rapor yazılmadı", empty, len(live))
        return EXIT_NO_PAIRS
    text = render_bridge_report(report, generated_at=now, since=args.since)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    LOGGER.info(
        "köprü: n=%d · karşılaştırılamayan=%d · yöntem=%s · rapor=%s",
        report.n,
        report.unmatched,
        report.method,
        args.out,
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    now = datetime.now(UTC)
    if args.command == "bridge":
        return _bridge(args, now)
    return _efficiency(args, now)


if __name__ == "__main__":
    raise SystemExit(main())
