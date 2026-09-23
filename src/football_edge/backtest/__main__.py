"""`python -m football_edge.backtest {selftest,select,walkforward}` — kilitli geliştirme verisinde.

`selftest`: bilinen sonuçlar. `select`: S bölgesinde hiperparametre seçimi →
`config/model_faz3.yaml` (controller commit'ler). `walkforward`: dondurulmuş yapılandırmayla E
bölgesi raporu.

Önce kilit: kilit dosyası bozuksa ya da önbellek kilitli dönemlerin özetinden farklıysa hiçbir
ölçüm koşmaz (exit 9). Sonra her denetim adıyla loglanır; kapı denetimlerinden biri kırmızıysa
exit 1 (history.yml adlandırır).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from football_edge.backtest.evaluate import DEFAULT_RESAMPLES
from football_edge.backtest.model_config import (
    MODEL_CONFIG_PATH,
    ModelConfig,
    ModelConfigError,
    dump_model_config,
    file_sha256,
    load_model_config,
)
from football_edge.backtest.selection import select
from football_edge.backtest.selftest import Check, run_selftest
from football_edge.backtest.wf_eval import summarise
from football_edge.backtest.wf_run import (
    development_groups,
    gap_penalty,
    render_walkforward,
    rows_digest,
    run_rows,
)
from football_edge.collect import configure_logging
from football_edge.db import connect
from football_edge.history.catalog import MAIN, Catalog, load_catalog
from football_edge.history.lock import LockViolation, load_lock
from football_edge.history.sync import load_matches
from football_edge.history.types import HistMatch
from football_edge.market.devig import DEFAULT_METHOD, METHODS

LOGGER = logging.getLogger("football_edge.backtest")
LOCK_PATH = Path("config/history_lock.yaml")
CATALOG_PATH = Path("config/history_leagues.yaml")
# 1: bir kapı denetimi kırmızı. Python'ın beklenmedik arızası da 1 verir; ayrım logdadır.
EXIT_GATE_FAILED = 1
# collect.EXIT_* (2–8) ile çakışmaz; history.yml'deki selftest adımı bu kodu adıyla karşılar.
EXIT_LOCK_VIOLATION = 9
# 10 köprünün (`market bridge`) "eşleşme yok"u; 11: model yapılandırması okunamadı ya da
# katalog/kilit yapılandırmadaki özetle uyuşmuyor — walk-forward koşmaz.
EXIT_CONFIG_MISMATCH = 11
DEFAULT_TAU = 0.02  # R139
DEFAULT_SENSITIVITY = (0.0, 0.05)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.backtest")
    commands = parser.add_subparsers(dest="command", required=True)
    selftest = commands.add_parser("selftest", help="bilinen sonuçlar K1–K4 (+ K2, D1 rapor)")
    selftest.add_argument("--lock", type=Path, default=LOCK_PATH)
    selftest.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    selftest.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD)
    selftest.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    chooser = commands.add_parser("select", help="S bölgesinde hiperparametre seçimi")
    chooser.add_argument("--lock", type=Path, default=LOCK_PATH)
    chooser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    chooser.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD)
    chooser.add_argument("--cadence-days", type=int, default=1)
    chooser.add_argument("--out", type=Path, default=MODEL_CONFIG_PATH)
    walk = commands.add_parser("walkforward", help="E bölgesi raporu (dondurulmuş yapılandırma)")
    walk.add_argument("--config", type=Path, default=MODEL_CONFIG_PATH)
    walk.add_argument("--lock", type=Path, default=LOCK_PATH)
    walk.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    walk.add_argument("--out", type=Path, required=True)
    walk.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    walk.add_argument("--gap", action="store_true", help="R128 boşluk cezası (iki ek koşu)")
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


def kinds_of(catalog: Catalog) -> Mapping[str, str]:
    return MappingProxyType({league.code: league.kind for league in catalog.leagues})


def _locked_matches(
    catalog_path: Path, lock_path: Path
) -> tuple[Catalog, Mapping[str, Sequence[HistMatch]]] | None:
    catalog = load_catalog(catalog_path)
    try:
        lock = load_lock(lock_path)
        with connect() as conn:
            return catalog, load_matches(conn, catalog, lock=lock)
    except LockViolation as error:
        LOGGER.error("kilit ihlali — koşulmadı: %s", "; ".join(error.differences))
        return None


def _select(args: argparse.Namespace) -> int:
    loaded = _locked_matches(args.catalog, args.lock)
    if loaded is None:
        return EXIT_LOCK_VIOLATION
    catalog, matches = loaded
    groups = rating_groups(catalog)
    elo, dc, trials = select(
        development_groups(matches, groups),
        kinds_of(catalog),
        groups,
        cadence_days=args.cadence_days,
        method=args.method,
    )
    for trial in trials:
        LOGGER.info("aday %s %s → S log loss %.6f", trial.model, dict(trial.params), trial.log_loss)
    config = ModelConfig(
        selected_at=datetime.now(UTC).date().isoformat(),
        catalog_sha256=file_sha256(args.catalog),
        lock_sha256=file_sha256(args.lock),
        method=args.method,
        elo=elo,
        dixon_coles=dc,
        cadence_days=args.cadence_days,
        tau=DEFAULT_TAU,
        sensitivity=DEFAULT_SENSITIVITY,
    )
    args.out.write_text(dump_model_config(config), encoding="utf-8")
    LOGGER.info("yazıldı: %s (%d aday)", args.out, len(trials))
    return 0


def _checked_config(args: argparse.Namespace) -> ModelConfig | None:
    try:
        config = load_model_config(args.config)
    except ModelConfigError as error:
        LOGGER.error("model yapılandırması: %s", error)
        return None
    for name, expected, path in (
        ("katalog", config.catalog_sha256, args.catalog),
        ("kilit", config.lock_sha256, args.lock),
    ):
        if file_sha256(path) != expected:
            LOGGER.error("%s değişti: %s yapılandırmadaki özetle uyuşmuyor", name, path)
            return None
    return config


def _walkforward(args: argparse.Namespace) -> int:
    config = _checked_config(args)
    if config is None:
        return EXIT_CONFIG_MISMATCH
    loaded = _locked_matches(args.catalog, args.lock)
    if loaded is None:
        return EXIT_LOCK_VIOLATION
    catalog, matches = loaded
    groups = rating_groups(catalog)
    development = development_groups(matches, groups)
    rows = run_rows(development, kinds_of(catalog), groups, config)
    summary = summarise(
        rows, tau=config.tau, sensitivity=config.sensitivity, resamples=args.resamples
    )
    gap = (
        gap_penalty(development, kinds_of(catalog), groups, config, resamples=args.resamples)
        if args.gap
        else None
    )
    args.out.write_text(
        render_walkforward(
            summary,
            config,
            generated_at=datetime.now(UTC),
            config_sha256=file_sha256(args.config),
            gap=gap,
            digest=rows_digest(rows),
        ),
        encoding="utf-8",
    )
    LOGGER.info("walk-forward raporu yazıldı: %s (E satırı %d)", args.out, summary.rows)
    return 0


COMMANDS: Mapping[str, Callable[[argparse.Namespace], int]] = MappingProxyType(
    {"selftest": _selftest, "select": _select, "walkforward": _walkforward}
)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
