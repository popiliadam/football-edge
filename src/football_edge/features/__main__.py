"""`python -m football_edge.features sync-news` — haber gözlemlerini `news_items`a taşır.

`collect-news` iş akışında toplamanın hemen ardından koşar (R172): `first_seen_at` bizim saatimizdir
ve toplamayla senkron arasındaki her dakika onu geç damgalar. Varsayılan pencere `SYNC_LOOKBACK`;
2026-09-04'ten beri biriken geçmiş bir kez `--since 2026-09-04` ile taşınır.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from types import MappingProxyType

from football_edge.collect import EXIT_SOURCE_FAILED, configure_logging
from football_edge.collector import ContractViolation
from football_edge.db import connect
from football_edge.features.news import SYNC_LOOKBACK, sync_news

LOGGER = logging.getLogger("football_edge.features")


def _utc(text: str) -> datetime:
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.features")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync-news")
    sync.add_argument("--since", type=_utc, default=None)
    return parser


def _sync_news(args: argparse.Namespace) -> int:
    try:
        with connect() as conn:
            written = sync_news(conn, since=args.since or _now() - SYNC_LOOKBACK)
            conn.commit()
    except ContractViolation as error:
        LOGGER.error("haber senkronu durdu: %s", error)
        return EXIT_SOURCE_FAILED
    LOGGER.info("haber: yeni %d", written)
    return 0


COMMANDS: Mapping[str, Callable[[argparse.Namespace], int]] = MappingProxyType(
    {"sync-news": _sync_news}
)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
