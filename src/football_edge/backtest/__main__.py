"""`python -m football_edge.backtest {selftest,select,walkforward}` — kilitli geliştirme verisinde.

`selftest`: bilinen sonuçlar. `select`: S bölgesinde hiperparametre seçimi →
`config/model_faz3.yaml` (controller commit'ler). `walkforward`: dondurulmuş yapılandırmayla E
bölgesi raporu. `final-eval --phase <faz>`: fazın TEK holdout açılışı (`backtest/final_eval.py`,
R135); gerçek açılış yalnız kanonik yollarla (16b).

Önce kilit: kilit dosyası bozuksa ya da önbellek kilitli dönemlerin özetinden farklıysa hiçbir
ölçüm koşmaz (exit 9). Sonra her denetim adıyla loglanır; kapı denetimlerinden biri kırmızıysa
exit 1 (history.yml adlandırır).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType

from football_edge.backtest.evaluate import DEFAULT_RESAMPLES
from football_edge.backtest.final_eval import (
    AlreadyOpened,
    OpenedButFailed,
    render_final,
    run_final,
    run_rehearsal,
)
from football_edge.backtest.model_config import (
    MODEL_CONFIG_PATH,
    ModelConfig,
    ModelConfigError,
    dump_model_config,
    file_sha256,
    load_model_config,
)
from football_edge.backtest.model_selftest import model_checks, model_rows
from football_edge.backtest.preregistration import (
    PHASES,
    CanonicalPaths,
    PreflightError,
    preflight,
    probe_out_dir,
    real_git,
)
from football_edge.backtest.selection import select
from football_edge.backtest.selftest import Check, run_selftest
from football_edge.backtest.walkforward import missing_reasons, rejected_prices
from football_edge.backtest.wf_eval import summarise
from football_edge.backtest.wf_run import (
    development_groups,
    gap_penalty,
    render_walkforward,
    rows_digest,
    run_rows,
)
from football_edge.collect import configure_logging
from football_edge.collector import ContractViolation
from football_edge.db import connect
from football_edge.history.catalog import MAIN, Catalog, kinds_of, load_catalog, rating_groups
from football_edge.history.holdout import DEV_END
from football_edge.history.lock import (
    EXIT_LOCK_VIOLATION,
    LockViolation,
    load_lock,
    refuse_on_violation,
)
from football_edge.history.sync import load_matches
from football_edge.history.types import HistMatch
from football_edge.market.devig import DEFAULT_METHOD, METHODS

LOGGER = logging.getLogger("football_edge.backtest")
LOCK_PATH = Path("config/history_lock.yaml")
CATALOG_PATH = Path("config/history_leagues.yaml")
# 1: bir kapı denetimi kırmızı. Python'ın beklenmedik arızası da 1 verir; ayrım logdadır.
EXIT_GATE_FAILED = 1
# 10 köprünün (`market bridge`) "eşleşme yok"u; 11: model yapılandırması okunamadı ya da
# katalog/kilit yapılandırmadaki özetle uyuşmuyor — walk-forward koşmaz.
EXIT_CONFIG_MISMATCH = 11
# final-eval: 12 ön kayıt denetimi tutmadı (AÇILMADI); 13 fazın açılışı zaten var (AÇILMADI);
# 14 AÇILDI ama değerlendirme tamamlanmadı (rapor yok) — HANDOFF'a adıyla, R135 yeniden koşusu.
EXIT_PREFLIGHT = 12
EXIT_ALREADY_OPENED = 13
EXIT_OPENED_FAILED = 14
DEFAULT_TAU = 0.02  # R139
REHEARSAL_START = date(2024, 7, 1)  # prova: E'nin son sezonu (R135)
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
    model = commands.add_parser("model-selftest", help="modelin bilinen sonuçları W1–W4")
    model.add_argument("--config", type=Path, default=MODEL_CONFIG_PATH)
    model.add_argument("--lock", type=Path, default=LOCK_PATH)
    model.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    model.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    final = commands.add_parser("final-eval", help="bir fazın tek, kayıtlı holdout açılışı")
    final.add_argument("--phase", choices=sorted(PHASES), required=True)
    # Varsayılanlar fazın kanonik yollarıdır (`canonical_paths`); başka yol yalnız provada geçer.
    final.add_argument("--prereg", type=Path, default=None)
    final.add_argument("--config", type=Path, default=None)
    final.add_argument("--lock", type=Path, default=LOCK_PATH)
    final.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    final.add_argument("--out", type=Path, required=True)
    final.add_argument("--rerun-reason", default=None)
    final.add_argument(
        "--rehearse",
        action="store_true",
        help="prova: E'nin son sezonu sahte holdout, anahtarsız, AÇILIŞ YOK",
    )
    return parser


def canonical_paths(phase: str) -> CanonicalPaths:
    """Fazın gerçek açılışının tek kabul ettiği yollar (16b); `faz3` için bugünkü varsayılanlar."""
    return CanonicalPaths(
        prereg=Path(f"config/{phase}_preregistration.yaml"),
        model=Path(f"config/model_{phase}.yaml"),
        lock=LOCK_PATH,
        catalog=CATALOG_PATH,
    )


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
        return refuse_on_violation(LOGGER, error, "bilinen sonuçlar koşulmadı")
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


def _locked_matches(
    catalog_path: Path, lock_path: Path
) -> tuple[Catalog, Mapping[str, Sequence[HistMatch]]] | None:
    catalog = load_catalog(catalog_path)
    try:
        lock = load_lock(lock_path)
        with connect() as conn:
            return catalog, load_matches(conn, catalog, lock=lock)
    except LockViolation as error:
        refuse_on_violation(LOGGER, error, "koşulmadı")  # çıkış kodunu çağıran verir
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
            missing=missing_reasons(development, rows, kinds_of(catalog)),
            rejected=rejected_prices(development, kinds_of(catalog), method=config.method),
        ),
        encoding="utf-8",
    )
    LOGGER.info("walk-forward raporu yazıldı: %s (E satırı %d)", args.out, summary.rows)
    return 0


def _model_selftest(args: argparse.Namespace) -> int:
    config = _checked_config(args)
    if config is None:
        return EXIT_CONFIG_MISMATCH
    loaded = _locked_matches(args.catalog, args.lock)
    if loaded is None:
        return EXIT_LOCK_VIOLATION
    catalog, matches = loaded
    groups = rating_groups(catalog)
    rows = model_rows(development_groups(matches, groups), kinds_of(catalog), groups, config)
    checks = model_checks(rows, resamples=args.resamples)
    for check in checks:
        _log(check)
    failed = [check.id for check in checks if check.gate and not check.passed]
    if failed:
        LOGGER.error("kırmızı model denetimi: %s", ", ".join(failed))
        return EXIT_GATE_FAILED
    LOGGER.info("model bilinen sonuçları: kapı denetimlerinin hepsi geçti")
    return 0


def _final_eval(args: argparse.Namespace) -> int:
    git = real_git()
    canonical = canonical_paths(args.phase)
    prereg_path: Path = args.prereg or canonical.prereg
    model_path: Path = args.config or canonical.model
    try:
        prereg = preflight(
            prereg_path=prereg_path,
            model_path=model_path,
            lock_path=args.lock,
            catalog_path=args.catalog,
            git=git,
            phase=args.phase,
            canonical=None if args.rehearse else canonical,
        )
        probe_out_dir(args.out)
        config = load_model_config(model_path)
        if args.rehearse:
            report = run_rehearsal(
                connect,
                catalog=load_catalog(args.catalog),
                lock=load_lock(args.lock),
                config=config,
                prereg=prereg,
                start=REHEARSAL_START,
                end=DEV_END,
            )
            args.out.write_text(
                render_final(report, generated_at=datetime.now(UTC)), encoding="utf-8"
            )
            LOGGER.info("prova raporu yazıldı: %s — holdout AÇILMADI", args.out)
            return 0
        report = run_final(
            connect,
            catalog=load_catalog(args.catalog),
            lock=load_lock(args.lock),
            config=config,
            prereg=prereg,
            prereg_sha256=file_sha256(prereg_path),
            git_sha=git.head(),
            now=datetime.now(UTC),
            report_path=args.out,
            rerun_reason=args.rerun_reason,
        )
    except (PreflightError, ModelConfigError, LockViolation, ContractViolation) as error:
        LOGGER.error("holdout AÇILMADI — ön denetim: %s", error)
        return EXIT_PREFLIGHT
    except AlreadyOpened as error:
        LOGGER.error("holdout AÇILMADI — %s", error)
        return EXIT_ALREADY_OPENED
    except OpenedButFailed as error:
        LOGGER.error("holdout AÇILDI ama rapor yazılmadı: %s", error)
        return EXIT_OPENED_FAILED
    try:
        args.out.write_text(render_final(report, generated_at=datetime.now(UTC)), encoding="utf-8")
    except Exception as error:
        LOGGER.error("holdout AÇILDI ama rapor yazılamadı: %s", error)
        return EXIT_OPENED_FAILED
    LOGGER.info("holdout raporu yazıldı: %s (amaç %s)", args.out, report.purpose)
    return 0


COMMANDS: Mapping[str, Callable[[argparse.Namespace], int]] = MappingProxyType(
    {
        "selftest": _selftest,
        "select": _select,
        "walkforward": _walkforward,
        "model-selftest": _model_selftest,
        "final-eval": _final_eval,
    }
)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
