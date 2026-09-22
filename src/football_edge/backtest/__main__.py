"""`python -m football_edge.backtest selftest` — kilitli geliştirme verisinde bilinen sonuçlar.

Önce kilit: kilit dosyası bozuksa ya da önbellek kilitli dönemlerin özetinden farklıysa hiçbir
ölçüm koşmaz (exit 9). Sonra her denetim adıyla loglanır; kapı denetimlerinden biri kırmızıysa
exit 1 (history.yml adlandırır).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from football_edge.backtest.evaluate import DEFAULT_RESAMPLES
from football_edge.backtest.selftest import Check, run_selftest
from football_edge.collect import configure_logging
from football_edge.db import connect
from football_edge.history.catalog import MAIN, Catalog, load_catalog
from football_edge.history.lock import LockViolation, load_lock
from football_edge.history.sync import load_matches
from football_edge.market.devig import DEFAULT_METHOD, METHODS

LOGGER = logging.getLogger("football_edge.backtest")
LOCK_PATH = Path("config/history_lock.yaml")
CATALOG_PATH = Path("config/history_leagues.yaml")
# 1: bir kapı denetimi kırmızı. Python'ın beklenmedik arızası da 1 verir; ayrım logdadır.
EXIT_GATE_FAILED = 1
# collect.EXIT_* (2–8) ile çakışmaz; history.yml'deki selftest adımı bu kodu adıyla karşılar.
EXIT_LOCK_VIOLATION = 9


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.backtest")
    commands = parser.add_subparsers(dest="command", required=True)
    selftest = commands.add_parser("selftest", help="bilinen sonuçlar K1–K4 (+ K2, D1 rapor)")
    selftest.add_argument("--lock", type=Path, default=LOCK_PATH)
    selftest.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    selftest.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD)
    selftest.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    return parser


def rating_groups(catalog: Catalog) -> Mapping[str, str]:
    """Elo'nun reyting grubu (R94): lig kodu → ülke. Elo'yu kuran her yol grupları buradan alır;
    selftest Elo kurmaz (K1–K4 fiyat ve Placebo ile ölçülür)."""
    return MappingProxyType({league.code: league.country for league in catalog.leagues})


def _log(check: Check) -> None:
    kind = "kapı" if check.gate else "rapor"
    verdict = "GEÇTİ" if check.passed else "KALDI"
    LOGGER.info("%s (%s) %s — %s", check.id, kind, verdict, check.detail)


def _selftest(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.catalog)
    try:
        lock = load_lock(args.lock)
        with connect() as conn:
            # Kilit, holdout dahil BÜTÜN satırlarda load_matches'in içinde doğrulanır (R96); dönen
            # yalnız geliştirme ve sonrası dönemidir — holdout history/'den anahtarsız çıkmaz.
            matches = load_matches(conn, catalog, lock=lock)
    except LockViolation as error:
        LOGGER.error("kilit ihlali — bilinen sonuçlar koşulmadı: %s", "; ".join(error.differences))
        return EXIT_LOCK_VIOLATION
    main_codes = frozenset(league.code for league in catalog.leagues if league.kind == MAIN)
    checks = run_selftest(
        matches, method=args.method, main_codes=main_codes, resamples=args.resamples
    )
    for check in checks:
        _log(check)
    failed = [check.id for check in checks if check.gate and not check.passed]
    if failed:
        LOGGER.error("kırmızı kapı denetimi: %s", ", ".join(failed))
        return EXIT_GATE_FAILED
    LOGGER.info("bilinen sonuçlar: kapı denetimlerinin hepsi geçti")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    return _selftest(_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
