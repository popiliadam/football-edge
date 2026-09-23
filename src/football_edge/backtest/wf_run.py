"""Walk-forward'u dondurulmuş yapılandırmayla koşturur ve raporlar (Faz 3 tasarımı §5.3).

Girdi `load_matches`in anahtarsız dönüşüdür (DEV + POST); burada yalnız DEV kalır — sonrası dönemi
spec §6.2'nin son ileri testidir ve hiçbir seçime girmez. Rapor yalnız toplu sayı taşır.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from types import MappingProxyType

from football_edge.backtest.harness import Strategy
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.selection import active_from
from football_edge.backtest.walkforward import (
    DC,
    DC_TOTALS,
    ELO,
    Row,
    group_matches,
    group_rows,
)
from football_edge.backtest.wf_eval import Score, Summary
from football_edge.history.holdout import DEV, Window, in_window, select_periods
from football_edge.history.types import TOTALS_25, HistMatch
from football_edge.market.metrics import (
    Interval,
    bootstrap_mean,
    interval_text,
    per_match_log_loss,
)
from football_edge.model.elo_model import EloModel
from football_edge.model.strategies import DixonColesStrategy


def development_groups(
    leagues: Mapping[str, Sequence[HistMatch]], rating_groups: Mapping[str, str]
) -> Mapping[str, tuple[HistMatch, ...]]:
    development = {
        code: select_periods(matches, periods=frozenset({DEV})) for code, matches in leagues.items()
    }
    return group_matches(development, rating_groups)


def model_strategies(
    matches: Sequence[HistMatch],
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: ModelConfig,
) -> Mapping[str, Strategy]:
    """Elo, Dixon-Coles 1X2 ve Ü/A; iki DC aynı memo'yu paylaşır (aynı veri, aynı fit)."""
    h2h = DixonColesStrategy(
        config=config.dixon_coles,
        groups=rating_groups,
        active_from=active_from(matches, kinds),
        cadence_days=config.cadence_days,
    )
    return {
        ELO: EloModel(config=config.elo, groups=rating_groups),
        DC: h2h,
        DC_TOTALS: DixonColesStrategy(
            config=h2h.config,
            groups=rating_groups,
            market=TOTALS_25,
            active_from=h2h.active_from,
            cadence_days=h2h.cadence_days,
            memo=h2h.memo,
        ),
    }


def run_rows(
    groups: Mapping[str, Sequence[HistMatch]],
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: ModelConfig,
) -> tuple[Row, ...]:
    return tuple(
        row
        for matches in groups.values()
        for row in group_rows(
            matches,
            kinds,
            model_strategies(matches, kinds, rating_groups, config),
            method=config.method,
        )
    )


# R128 boşluk cezası (DEV simülasyonu): E'nin bir sezonu girdiden çıkarılır, sonraki sezon iki
# koşuda aynı maçlarda ölçülür. Canlı ve anahtarsız yollar holdout yılını böyle atlar.
GAP_SKIPPED = Window(date(2022, 7, 1), date(2023, 7, 1))
GAP_MEASURED = Window(date(2023, 7, 1), date(2024, 7, 1))


def gap_penalty(
    groups: Mapping[str, Sequence[HistMatch]],
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: ModelConfig,
    *,
    resamples: int,
    skipped: Window = GAP_SKIPPED,
    measured: Window = GAP_MEASURED,
) -> Mapping[str, Interval]:
    """Bileşen → ölçülen sezonda maç başına LL(boşluklu) − LL(tam), eşleşen satırlarda."""
    full = run_rows(groups, kinds, rating_groups, config)
    cut = {name: tuple(m for m in ms if not in_window(m, skipped)) for name, ms in groups.items()}
    gapped = {row.key: row for row in run_rows(cut, kinds, rating_groups, config)}
    found: dict[str, Interval] = {}
    for name in (ELO, DC):
        pairs = [
            (row, gapped[row.key])
            for row in full
            if measured.start is not None
            and measured.start <= row.key.date < measured.end
            and row.key in gapped
            and name in row.components
            and name in gapped[row.key].components
        ]
        if not pairs:
            continue
        outcomes = [row.outcome for row, _ in pairs]
        before = per_match_log_loss([row.components[name] for row, _ in pairs], outcomes)
        after = per_match_log_loss([other.components[name] for _, other in pairs], outcomes)
        found[name] = bootstrap_mean(
            [b - a for a, b in zip(before, after, strict=True)], resamples=resamples
        )
    return MappingProxyType(found)


def rows_digest(rows: Sequence[Row]) -> str:
    """Satırların (anahtar, bölge, bileşen olasılıkları 1e-9'a yuvarlı) sha256'sı — tasarım §5.3."""
    lines = (
        f"{row.key}|{row.zone}|"
        + ",".join(f"{p:.9f}" for name in sorted(row.components) for p in row.components[name])
        for row in sorted(rows, key=lambda r: (r.key, r.zone))
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def format_interval(interval: Interval | None) -> str:
    return "ölçülemedi" if interval is None else interval_text(interval)


def format_counts(counts: Mapping[str, int]) -> str:
    return " · ".join(f"{name} {count}" for name, count in counts.items()) or "yok"


def _score_line(score: Score) -> str:
    calibration = (
        "ölçülemedi"
        if score.calibration is None
        else f"b={score.calibration.slope:.3f} ECE={score.calibration.ece:.4f}"
    )
    rps = "—" if score.rps is None else f"{score.rps:.4f}"
    loss = format_interval(score.log_loss)
    return (
        f"| {score.name} | {score.n} | {loss} | {score.brier:.4f} | {rps} | "
        f"{calibration} | {format_interval(score.clv)} | {score.bets} |"
    )


def score_table(title: str, scores: Mapping[str, Score]) -> list[str]:
    if not scores:
        return [f"### {title}", "", "ölçülemedi: satır yok", ""]
    return [
        f"### {title}",
        "",
        "| strateji | n | log loss [%95] | Brier | RPS | kalibrasyon | CLV [%95] | bahis |",
        "|---|---|---|---|---|---|---|---|",
        *(_score_line(score) for score in scores.values()),
        "",
    ]


def render_walkforward(
    summary: Summary,
    config: ModelConfig,
    *,
    generated_at: datetime,
    config_sha256: str,
    gap: Mapping[str, Interval] | None = None,
    digest: str | None = None,
    missing: Mapping[str, int] | None = None,
    rejected: Mapping[str, int] | None = None,
) -> str:
    lines = [
        f"# Faz 3 walk-forward raporu — {generated_at.date().isoformat()}",
        "",
        f"Üretim: {generated_at.isoformat()} · `config/model_faz3.yaml` sha256 `{config_sha256}` · "
        f"vig `{config.method}` · τ = {config.tau} · satır özeti sha256 `{digest or 'yok'}`. "
        "Yalnız geliştirme dönemi (E bölgesi); "
        "holdout ve sonrası dönemi okunmadı. Toplu sayılar; maç satırı yok.",
        "",
        f"E satırı {summary.rows} · bileşeni eksik (ortak kümeye girmedi) {summary.incomplete} · "
        f"geri düşülen ağırlık katı {len(summary.fallback)}",
        *(
            [f"Ortak kümeye girmeyen ana lig maçı (nedene göre): {format_counts(missing)}"]
            if missing is not None
            else []
        ),
        *(
            [f"Vig'i temizlenemeyen fiyat kümesi (Σ 1/o < 1 dahil): {format_counts(rejected)}"]
            if rejected is not None
            else []
        ),
        "",
        *score_table("Ana ligler, 1X2 (ortak satırlar)", summary.main),
        f"ΔLL harman − piyasa: {format_interval(summary.blend_gap)}",
        "",
        "| lig | ΔLL harman − piyasa [%95] |",
        "|---|---|",
        *(f"| {league} | {format_interval(gap)} |" for league, gap in summary.league_gaps.items()),
        "",
        *score_table("Ek ligler, 1X2 (yalnız model; kapanış kıyas)", summary.extra),
        *score_table("Ana ligler, Ü/A 2.5 (ikincil)", summary.totals),
        "### CLV duyarlılığı (harman)",
        "",
        *(
            f"- τ = {tau}: {format_interval(interval)}"
            for tau, interval in summary.clv_sensitivity.items()
        ),
        "",
    ]
    if gap is not None:
        lines += [
            "### Boşluk cezası (R128, DEV simülasyonu)",
            "",
            f"{GAP_SKIPPED.start}–{GAP_SKIPPED.end} sezonu girdiden çıkarıldı; "
            f"{GAP_MEASURED.start}–{GAP_MEASURED.end} maçlarında LL(boşluklu) − LL(tam):",
            "",
            *(f"- {name}: {format_interval(interval)}" for name, interval in gap.items()),
            "",
        ]
    return "\n".join(lines)
