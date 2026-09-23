"""Bir fazın TEK, kayıtlı holdout açılışı (Faz 3 tasarımı §8; R128, R130, R135).

`open_holdout`ın anılabildiği TEK modül (`tests/test_holdout_access_rule.py`). Anahtar yalnız
`load_matches`e verilir ve hemen bırakılır: değerlendirme anahtarı değil SEÇİLMİŞ SATIRLARI alır
(DEFERRED 12i). Açılıştan önce ön kayıt denetimi (`preflight`) ve açılış sayımı: aynı faz için
önceki bir açılış varsa açılmaz — yalnız çöküş sonrası, rapor üretilmemişse ve git SHA'sı aynıysa
tek bir kayıtlı yeniden koşu (`<faz>-rerun`). Veritabanında `0010`un tekil indeksi ikinci
katmandır. Faz ön kaydın `phase` alanından gelir (16d).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from functools import partial
from pathlib import Path
from typing import Any

import psycopg

from football_edge.backtest.evaluate import clv_values
from football_edge.backtest.harness import replay
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.preregistration import Preregistration
from football_edge.backtest.strategies import EloPointInTime, Placebo
from football_edge.backtest.walkforward import (
    ELO_SCAFFOLD,
    Row,
    group_matches,
    group_rows,
    zone_of,
)
from football_edge.backtest.wf_eval import Summary, frozen_weights, summarise
from football_edge.backtest.wf_run import format_interval, model_strategies, score_table
from football_edge.history.catalog import Catalog
from football_edge.history.holdout import HOLDOUT, POST, open_holdout, period_of
from football_edge.history.lock import HistoryLock
from football_edge.history.sync import load_matches
from football_edge.history.types import HistMatch
from football_edge.market.devig import devig
from football_edge.market.metrics import Interval, bootstrap_mean

# 0010'un tekil indeksiyle aynı ifade: `purpose`un ilk alanı fazın ya da yeniden koşusunun TAM adı.
# `LIKE 'faz3%'` `faz30`u da sayardı (16d).
_OPENINGS = (
    "SELECT purpose, git_sha FROM holdout_access_log "
    "WHERE split_part(purpose, ':', 1) IN (%s, %s) ORDER BY id"
)


class AlreadyOpened(RuntimeError):
    """Fazın holdout'u zaten açıldı; yeniden koşu kuralı karşılanmadı."""


class OpenedButFailed(RuntimeError):
    """Açılış KAYDA DÜŞTÜ ama değerlendirme tamamlanmadı: rapor yazılmaz, HANDOFF adıyla sayar."""


class HoldoutCountMismatch(OpenedButFailed):
    """Açılan holdout satır sayısı kilitteki sayıdan farklı."""


@dataclass(frozen=True)
class FinalReport:
    purpose: str
    holdout: Summary
    post: Summary
    placebo_holdout: Interval | None
    placebo_post: Interval | None
    holdout_rows: int
    predictions_sha256: str


def rerun_of(phase: str) -> str:
    return f"{phase}-rerun"


def previous_openings(conn: psycopg.Connection[Any], *, phase: str) -> tuple[tuple[str, str], ...]:
    with conn.cursor() as cur:
        cur.execute(_OPENINGS, (phase, rerun_of(phase)))
        return tuple((str(row[0]), str(row[1])) for row in cur.fetchall())


def purpose_for(
    previous: Sequence[tuple[str, str]],
    *,
    phase: str,
    prereg_sha256: str,
    git_sha: str,
    report_exists: bool,
    rerun_reason: str | None,
) -> str:
    """İlk açılış `<faz>:<sha>`; yeniden koşu YALNIZ tek ilk açılıştan sonra, rapor yokken, aynı
    SHA ile ve adıyla (`<faz>-rerun:<neden>:<sha>`)."""
    if not previous:
        if rerun_reason is not None:
            raise AlreadyOpened("yeniden koşu istendi ama önceki açılış yok")
        return f"{phase}:{prereg_sha256}"
    if rerun_reason is None or not rerun_reason.strip():
        raise AlreadyOpened(f"{phase} holdout'u zaten açıldı ({len(previous)} kayıt)")
    if len(previous) != 1 or report_exists or previous[0][1] != git_sha:
        raise AlreadyOpened("yeniden koşu kuralı: tek açılış, rapor yok ve aynı git SHA'sı")
    return f"{rerun_of(phase)}:{rerun_reason.strip()}:{prereg_sha256}"


def check_holdout_count(lock: HistoryLock, leagues: Mapping[str, Sequence[HistMatch]]) -> int:
    expected = sum(periods[HOLDOUT].rows for periods in lock.leagues.values() if HOLDOUT in periods)
    found = sum(1 for matches in leagues.values() for m in matches if period_of(m.date) == HOLDOUT)
    if found != expected:
        raise HoldoutCountMismatch(f"holdout satırı {found}, kilitte {expected}")
    return found


def final_zone(match: HistMatch, kind: str) -> str | None:
    """Geliştirmede S/E (ağırlıklar yalnız buradan), sonra holdout ve sonrası bölgeleri."""
    period = period_of(match.date)
    return zone_of(match, kind) if period not in (HOLDOUT, POST) else period


Zoning = Callable[[HistMatch, str], str | None]


def rehearsal_zone(start: date, end: date) -> Zoning:
    """Prova (R135): [start, end) sahte holdout — geliştirme döneminin içinde, anahtarsız."""

    def zone(match: HistMatch, kind: str) -> str | None:
        if start <= match.date < end:
            return HOLDOUT
        return zone_of(match, kind)

    return zone


def _placebo(
    groups: Mapping[str, Sequence[HistMatch]],
    method: str,
    zone: Callable[[HistMatch], str | None],
) -> tuple[Interval | None, Interval | None]:
    """Placebo'nun holdout ve sonrası CLV'si (C3'ün yanındaki negatif kontrol)."""
    found: dict[str, list[float]] = {HOLDOUT: [], POST: []}
    for matches in groups.values():
        result = replay(matches, Placebo(devig=partial(devig, method=method)))
        for period, values in found.items():
            chosen = tuple(p for p in result.predictions if zone(matches[p.match_index]) == period)
            values.extend(clv_values(replace(result, predictions=chosen), method=method))
    holdout, post = (
        bootstrap_mean(values) if values else None for values in (found[HOLDOUT], found[POST])
    )
    return holdout, post


def evaluate_selected(
    leagues: Mapping[str, Sequence[HistMatch]],
    *,
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: ModelConfig,
    prereg: Preregistration,
    purpose: str,
    zoning: Zoning = final_zone,
) -> FinalReport:
    """Anahtar görmez: seçilmiş satırlar (DEV + HOLDOUT + POST) tam durumla oynatılır."""
    groups = group_matches(leagues, rating_groups)
    rows: list[Row] = []
    for matches in groups.values():
        strategies = {
            **model_strategies(matches, kinds, rating_groups, config),
            ELO_SCAFFOLD: EloPointInTime(groups=rating_groups),
        }
        rows.extend(group_rows(matches, kinds, strategies, method=config.method, zoning=zoning))
    targets = [(row.key.league, row.season) for row in rows if row.zone in (HOLDOUT, POST)]
    weights = frozen_weights(rows, targets)
    holdout, post = (
        summarise(
            rows,
            tau=prereg.tau,
            sensitivity=prereg.sensitivity,
            resamples=prereg.resamples,
            zone=zone,
            given=weights,
        )
        for zone in (HOLDOUT, POST)
    )
    placebo_holdout, placebo_post = _placebo(
        groups, config.method, lambda match: zoning(match, kinds[match.league])
    )
    digest = hashlib.sha256(
        "\n".join(
            f"{row.key}|{row.zone}|"
            + ",".join(f"{p:.9f}" for c in sorted(row.components) for p in row.components[c])
            for row in sorted(rows, key=lambda r: (r.key, r.zone))
            if row.zone in (HOLDOUT, POST)
        ).encode("utf-8")
    ).hexdigest()
    return FinalReport(
        purpose=purpose,
        holdout=holdout,
        post=post,
        placebo_holdout=placebo_holdout,
        placebo_post=placebo_post,
        holdout_rows=sum(1 for row in rows if row.zone == HOLDOUT),
        predictions_sha256=digest,
    )


def run_final(
    connect: Callable[[], psycopg.Connection[Any]],
    *,
    catalog: Catalog,
    lock: HistoryLock,
    config: ModelConfig,
    prereg: Preregistration,
    prereg_sha256: str,
    git_sha: str,
    now: datetime,
    report_path: Path,
    rerun_reason: str | None = None,
) -> FinalReport:
    """Kilit, yineleme ve sayım (açılıştan ÖNCE) → TAZE bağlantıda tek açılış → seçilmiş satırlar.

    Açılış kayda düştükten sonraki HER arıza `OpenedButFailed`dır (exit 14): yeniden koşu kuralı
    (R135) yalnız bu sınıfa bakar. 0010'un ikinci açılışı reddetmesi açılış değildir (exit 13).
    Süreç dışı ölüm (OOM, 137) burada yakalanamaz: Task 13'ün tablosu onu "kaydı say" diye okur.
    """
    with connect() as conn:
        # Kilit ve yineleme (C1) holdout dahil AÇILIŞTAN ÖNCE: ihlal açılış harcamaz.
        load_matches(conn, catalog, lock=lock)
        purpose = purpose_for(
            previous_openings(conn, phase=prereg.phase),
            phase=prereg.phase,
            prereg_sha256=prereg_sha256,
            git_sha=git_sha,
            report_exists=report_path.exists(),
            rerun_reason=rerun_reason,
        )
    opened = False
    try:
        with connect() as conn:
            try:
                key = open_holdout(conn, purpose=purpose, git_sha=git_sha, now=now)
            except psycopg.errors.UniqueViolation as error:
                raise AlreadyOpened(f"0010 ikinci açılışı reddetti: {error}") from error
            opened = True
            try:
                leagues = load_matches(conn, catalog, lock=lock, key=key)
            except Exception as error:
                raise OpenedButFailed(f"açılıştan sonra yükleme düştü: {error}") from error
            del key
    except OpenedButFailed:
        raise
    except Exception as error:
        # Bağlantının kapanışı (`__exit__` → commit) açılıştan SONRA düşerse de exit 14 (P15).
        if not opened:
            raise
        raise OpenedButFailed(
            f"açılıştan sonra bağlantı düştü: {type(error).__name__}: {error}"
        ) from error
    try:
        check_holdout_count(lock, leagues)
        return evaluate_selected(
            leagues,
            kinds={league.code: league.kind for league in catalog.leagues},
            rating_groups={league.code: league.country for league in catalog.leagues},
            config=config,
            prereg=prereg,
            purpose=purpose,
        )
    except OpenedButFailed:
        raise
    except Exception as error:
        raise OpenedButFailed(
            f"açılıştan sonra değerlendirme düştü: {type(error).__name__}: {error}"
        ) from error


def render_final(report: FinalReport, *, generated_at: datetime) -> str:
    """Yalnız toplu sayı; ham satır yok. C1–C6 ön kayıttaki adlarıyla."""
    return "\n".join(
        [
            f"# Faz 3 holdout raporu — {generated_at.date().isoformat()}",
            "",
            f"Açılış amacı `{report.purpose}` · holdout satırı {report.holdout_rows} · tahmin "
            f"özeti sha256 `{report.predictions_sha256}`. Tek açılış (R135); ağırlıklar ve "
            "hiperparametreler yalnız geliştirme döneminden.",
            "",
            *score_table("C1–C4 · holdout, ana ligler, 1X2 (ortak satırlar)", report.holdout.main),
            f"C1 ΔLL harman − piyasa: {format_interval(report.holdout.blend_gap)}",
            f"C3 Placebo CLV (negatif kontrol): {format_interval(report.placebo_holdout)}",
            "",
            *score_table("Holdout, ek ligler (yalnız model)", report.holdout.extra),
            *score_table("C5 · holdout, Ü/A 2.5", report.holdout.totals),
            *score_table("C6 · sonrası dönemi, tam durum", report.post.main),
            f"C6 ΔLL harman − piyasa: {format_interval(report.post.blend_gap)}",
            f"C6 Placebo CLV: {format_interval(report.placebo_post)}",
            "",
        ]
    )


def run_rehearsal(
    connect: Callable[[], psycopg.Connection[Any]],
    *,
    catalog: Catalog,
    lock: HistoryLock,
    config: ModelConfig,
    prereg: Preregistration,
    start: date,
    end: date,
) -> FinalReport:
    """Açılışın bütün yolu, anahtarsız ve kayıtsız: E'nin son sezonu sahte holdout olur."""
    with connect() as conn:
        leagues = load_matches(conn, catalog, lock=lock)
    return evaluate_selected(
        leagues,
        kinds={league.code: league.kind for league in catalog.leagues},
        rating_groups={league.code: league.country for league in catalog.leagues},
        config=config,
        prereg=prereg,
        purpose="prova",
        zoning=rehearsal_zone(start, end),
    )
