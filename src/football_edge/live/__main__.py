"""`python -m football_edge.live {shadow,parity,freeze-weights,report}` — canlı gölge.

`shadow`: kararı verilmiş, başlamamış maçlar → `model_predictions` (yayın yok, kredi yok).
`parity`: sonrası dönemde hem defterde hem tabanda olan maçların yapısal alanları (lig, tarih,
adlar, sezon, başlama) birebir mi — fark varsa exit 15. Fiyat farkı rapordur, kapı değil.
`freeze-weights`: geliştirme E satırlarıyla harman ağırlığı → `config/blend_weights_faz3.yaml`
(controller koşar ve commit'ler); havuz fit edilemezse exit 18, dosya yazılmaz.
`report`: baz serisinin haftalık gölge CLV raporu (Faz 4 T0a).
"""

from __future__ import annotations

import argparse
import logging
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType

from football_edge.backtest.__main__ import (
    CATALOG_PATH,
    EXIT_CONFIG_MISMATCH,
    LOCK_PATH,
)
from football_edge.backtest.context import record_of
from football_edge.backtest.evaluate import DEFAULT_RESAMPLES
from football_edge.backtest.model_config import (
    MODEL_CONFIG_PATH,
    ModelConfig,
    ModelConfigError,
    file_sha256,
    load_model_config,
)
from football_edge.backtest.records import MatchKey
from football_edge.backtest.walkforward import group_matches
from football_edge.backtest.wf_run import development_groups, run_rows
from football_edge.collect import configure_logging
from football_edge.db import connect
from football_edge.history.catalog import MAIN, Catalog, kinds_of, load_catalog, rating_groups
from football_edge.history.holdout import HOLDOUT_END
from football_edge.history.lock import LockViolation, load_lock, refuse_on_violation
from football_edge.history.sync import load_matches
from football_edge.history.types import HistMatch
from football_edge.live.context import LiveMatch, build_batch, live_key, naming_from, season_of
from football_edge.live.report import build_report, outcomes_of, render_report
from football_edge.live.shadow import shadow_rows, write_shadow
from football_edge.live.store import (
    BASE_STRATEGIES,
    load_closing,
    load_live_matches,
    load_predictions,
    load_quotes,
)
from football_edge.live.weights import (
    BLEND_WEIGHTS_PATH,
    BlendWeightsError,
    PooledFitFailed,
    dump_blend_weights,
    fallback_reasons,
    freeze,
    load_blend_weights,
)
from football_edge.market.bridge import load_aliases

LOGGER = logging.getLogger("football_edge.live")
ALIASES_PATH = Path("config/history_aliases.yaml")
HORIZON = timedelta(days=8)
LOOKBACK = timedelta(days=10)
EXIT_PARITY = 15
# `freeze-weights`: havuz ağırlığı fit edilemedi (son inceleme I-2); 16/17 Jev bütçesi/anahtarı.
EXIT_POOLED_UNFIT = 18
# Saat dilimi ya da yaz saati hatası ≥ 60 dk kaydırır; yayıncı kaynaklı küçük saat farkları değil.
KICKOFF_TOLERANCE = timedelta(minutes=30)
# Faz 3 gölge serisi bu tarihten sonra başladı; seri `model_config_sha256` ile ayrılır (R161).
REPORT_SINCE = datetime(2026, 9, 1, tzinfo=UTC)


def head_sha() -> str:
    return subprocess.run(
        ("git", "rev-parse", "HEAD"), capture_output=True, text=True, check=True
    ).stdout.strip()


def _utc(text: str) -> datetime:
    """Saat dilimsiz tarih UTC sayılır; dilimli olan UTC'ye ÇEVRİLİR (dilimi silinmez)."""
    found = datetime.fromisoformat(text)
    return found.replace(tzinfo=UTC) if found.tzinfo is None else found.astimezone(UTC)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.live")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("shadow", "parity"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, default=MODEL_CONFIG_PATH)
        command.add_argument("--lock", type=Path, default=LOCK_PATH)
        command.add_argument("--catalog", type=Path, default=CATALOG_PATH)
        command.add_argument("--aliases", type=Path, default=ALIASES_PATH)
    commands.choices["parity"].add_argument(
        "--since",
        type=lambda text: datetime.fromisoformat(text).replace(tzinfo=UTC),
        default=datetime.combine(HOLDOUT_END, datetime.min.time(), tzinfo=UTC),
    )
    frozen = commands.add_parser("freeze-weights", help="E satırlarıyla donmuş harman ağırlığı")
    frozen.add_argument("--config", type=Path, default=MODEL_CONFIG_PATH)
    frozen.add_argument("--lock", type=Path, default=LOCK_PATH)
    frozen.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    frozen.add_argument("--out", type=Path, default=BLEND_WEIGHTS_PATH)
    report = commands.add_parser("report", help="baz serisinin haftalık gölge CLV raporu")
    report.add_argument("--config", type=Path, default=MODEL_CONFIG_PATH)
    report.add_argument("--lock", type=Path, default=LOCK_PATH)
    report.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    report.add_argument("--weights", type=Path, default=BLEND_WEIGHTS_PATH)
    report.add_argument("--out", type=Path, required=True)
    report.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    report.add_argument("--since", type=_utc, default=REPORT_SINCE)
    return parser


def _codes(catalog: Catalog) -> Mapping[str, str]:
    return MappingProxyType({league.league_id: league.code for league in catalog.leagues})


def _shadow(args: argparse.Namespace) -> int:
    config = _frozen_config(args)
    if config is None:
        return EXIT_CONFIG_MISMATCH
    catalog = load_catalog(args.catalog)
    now = datetime.now(UTC)
    try:
        with connect() as conn:
            history = load_matches(conn, catalog, lock=load_lock(args.lock))
            # 16f (B2): bayat koruması karara göre LOOKBACK geriye bakar; defter bir gün daha
            # geriden yüklenir ki elle geç koşuda korumanın gördüğü maç eksik kalmasın.
            live = load_live_matches(
                conn, since=now - LOOKBACK - timedelta(days=1), until=now + HORIZON
            )
            quotes = load_quotes(
                conn, tuple(m.match_id for m in live if m.kickoff > now), until=now
            )
            groups = rating_groups(catalog)
            batch = build_batch(
                live,
                quotes,
                group_matches(history, groups),
                now=now,
                naming=naming_from(history, _codes(catalog), load_aliases(args.aliases)),
                kinds=kinds_of(catalog),
                rating_groups=groups,
            )
            rows = shadow_rows(
                batch,
                config=config,
                rating_groups=groups,
                config_sha256=file_sha256(args.config),
                git_sha=head_sha(),
            )
            written = write_shadow(conn, rows)
    except LockViolation as error:
        return refuse_on_violation(LOGGER, error, "gölge tahmin koşulmadı")
    LOGGER.info(
        "gölge: karar %d · yazılan satır %d · eşlenemeyen %d · bayat durum %d · fiyatsız %d",
        len(batch.decisions),
        written,
        len(batch.unmapped),
        len(batch.stale),
        len(batch.no_quote),
    )
    return 0


@dataclass(frozen=True)
class ParityReport:
    paired: int
    unmatched: int
    season_mismatch: int
    kickoff_mismatch: int


def parity(
    live: Sequence[LiveMatch],
    history: Mapping[str, Sequence[HistMatch]],
    *,
    codes: Mapping[str, str],
    aliases: Mapping[str, str],
    kinds: Mapping[str, str],
) -> ParityReport:
    """E3: defterdeki maç ↔ taban satırı yapısal alanları (fiyat hariç)."""
    naming = naming_from(history, codes, aliases)
    index: dict[MatchKey, HistMatch] = {
        record_of(match).key: match for matches in history.values() for match in matches
    }
    paired = unmatched = seasons = kickoffs = 0
    for match in live:
        key = live_key(match, naming)
        found = None if key is None else index.get(key)
        if key is None or found is None:
            unmatched += 1
            continue
        paired += 1
        league = [m for m in history.get(key.league, ()) if m is not found]
        if season_of(league, key.date, kinds.get(key.league, "")) not in (None, found.season):
            seasons += 1
        if found.kickoff is not None and abs(found.kickoff - match.kickoff) > KICKOFF_TOLERANCE:
            kickoffs += 1
    return ParityReport(paired, unmatched, seasons, kickoffs)


def _parity(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.catalog)
    try:
        with connect() as conn:
            history = load_matches(conn, catalog, lock=load_lock(args.lock))
            live = load_live_matches(conn, since=args.since, until=datetime.now(UTC))
    except LockViolation as error:
        return refuse_on_violation(LOGGER, error, "eşitlik raporu koşulmadı")
    report = parity(
        live,
        history,
        codes=_codes(catalog),
        aliases=load_aliases(args.aliases),
        kinds=kinds_of(catalog),
    )
    LOGGER.info(
        "eşitlik (E3): eşleşen %d · eşlenemeyen %d · sezon farkı %d · başlama farkı %d",
        report.paired,
        report.unmatched,
        report.season_mismatch,
        report.kickoff_mismatch,
    )
    if report.season_mismatch or report.kickoff_mismatch:
        LOGGER.error("yapısal alan farkı: canlı bağlam tarihsel bağlamla aynı değil")
        return EXIT_PARITY
    return 0


def _frozen_config(args: argparse.Namespace) -> ModelConfig | None:
    """Model yapılandırması, katalog ve kilit dosyadaki özetle aynı mı; değilse None (exit 11)."""
    try:
        config = load_model_config(args.config)
    except ModelConfigError as error:
        LOGGER.error("model yapılandırması: %s", error)
        return None
    if (file_sha256(args.catalog), file_sha256(args.lock)) != (
        config.catalog_sha256,
        config.lock_sha256,
    ):
        LOGGER.error("katalog ya da kilit model yapılandırmasındaki özetle uyuşmuyor")
        return None
    return config


def _freeze_weights(args: argparse.Namespace) -> int:
    config = _frozen_config(args)
    if config is None:
        return EXIT_CONFIG_MISMATCH
    catalog = load_catalog(args.catalog)
    try:
        with connect() as conn:
            # Anahtarsız: holdout dönmez; ağırlık yalnız DEV'in E satırlarından (R161).
            history = load_matches(conn, catalog, lock=load_lock(args.lock))
    except LockViolation as error:
        return refuse_on_violation(LOGGER, error, "ağırlık dondurulmadı")
    groups = rating_groups(catalog)
    rows = run_rows(development_groups(history, groups), kinds_of(catalog), groups, config)
    try:
        weights = freeze(
            rows,
            [league.code for league in catalog.leagues if league.kind == MAIN],
            model_config_sha256=file_sha256(args.config),
            lock_sha256=config.lock_sha256,
            catalog_sha256=config.catalog_sha256,
        )
    except PooledFitFailed as error:
        LOGGER.error("harman ağırlığı dondurulmadı, dosya yazılmadı: %s", error)
        return EXIT_POOLED_UNFIT
    args.out.write_text(dump_blend_weights(weights), encoding="utf-8")
    for league, reason in fallback_reasons(rows, weights).items():
        LOGGER.info("havuza düşen lig %s: %s", league, reason)
    LOGGER.info(
        "harman ağırlığı yazıldı: %s (kendi ağırlığı %d lig · havuza düşen %d)",
        args.out,
        len(weights.leagues),
        len(weights.fallback),
    )
    return 0


def _report(args: argparse.Namespace) -> int:
    config = _frozen_config(args)
    if config is None:
        return EXIT_CONFIG_MISMATCH
    try:
        weights = load_blend_weights(args.weights)
    except BlendWeightsError as error:
        LOGGER.error("harman ağırlığı: %s", error)
        return EXIT_CONFIG_MISMATCH
    config_sha256 = file_sha256(args.config)
    if (weights.model_config_sha256, weights.lock_sha256, weights.catalog_sha256) != (
        config_sha256,
        config.lock_sha256,
        config.catalog_sha256,
    ):
        LOGGER.error("harman ağırlığı başka bir model yapılandırmasıyla dondurulmuş")
        return EXIT_CONFIG_MISMATCH
    catalog = load_catalog(args.catalog)
    now = datetime.now(UTC)
    try:
        with connect() as conn:
            # Sonuç gölge modelin kendi kaynağından: anahtarsız taban (DEV + POST, holdout yok).
            history = load_matches(conn, catalog, lock=load_lock(args.lock))
            predictions = load_predictions(
                conn,
                since=args.since,
                strategies=BASE_STRATEGIES,
                model_config_sha256=config_sha256,
            )
            closing = load_closing(conn, tuple(sorted({row.match_id for row in predictions})))
            fixtures = load_live_matches(conn, since=args.since, until=now)
    except LockViolation as error:
        return refuse_on_violation(LOGGER, error, "gölge raporu koşulmadı")
    codes = _codes(catalog)
    report = build_report(
        predictions,
        closing,
        outcomes_of(history),
        weights,
        tau=config.tau,
        method=config.method,
        resamples=args.resamples,
        fixtures=MappingProxyType(
            {match.match_id: codes.get(match.league_id, match.league_id) for match in fixtures}
        ),
    )
    args.out.write_text(render_report(report, generated_at=now), encoding="utf-8")
    LOGGER.info(
        "gölge raporu: karar %d · sonuçlu %d · kapanışlı %d · bahis %d",
        report.decided,
        report.settled,
        report.closed,
        report.bets,
    )
    return 0


COMMANDS: Mapping[str, Callable[[argparse.Namespace], int]] = MappingProxyType(
    {
        "shadow": _shadow,
        "parity": _parity,
        "freeze-weights": _freeze_weights,
        "report": _report,
    }
)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
