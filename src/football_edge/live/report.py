"""Haftalık gölge CLV raporu (Faz 4 tasarımı §2 T0a; DEFERRED 16o, 16e).

Girdi `model_predictions`in BAZ satırlarıdır (`store.BASE_STRATEGIES`); harman, donmuş ağırlıkla
(`live/weights.py`) burada kurulur. Kapanış mühürlü defterin `is_closing` turudur; sonuç
football-data tarihsel tabanından (`outcomes_of`, anahtar `match_key`) — defterin `match_results`i
dolmaz. Rapor yalnız toplu sayı basar. Jev'li stratejiyle
fark bu modülde HESAPLANMAZ (spec §5/5): mühür testi `tests/test_live_report.py`de.
Veritabanına dokunmaz — okuyucular `live/store.py`de.
"""

from __future__ import annotations

import contextlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from football_edge.backtest.context import record_of
from football_edge.backtest.walkforward import BLEND_COMPONENTS, MARKET
from football_edge.backtest.wf_eval import bet_clv
from football_edge.backtest.wf_run import format_interval
from football_edge.history.types import RESULTS, HistMatch
from football_edge.live.context import match_key_text
from football_edge.live.store import BASE_STRATEGIES, PredictionRow
from football_edge.live.weights import BlendWeights, weights_for
from football_edge.market.devig import InvalidPrices, devig
from football_edge.market.metrics import Interval, bootstrap_mean, per_match_log_loss
from football_edge.model.pool import pool


@dataclass(frozen=True)
class LeagueCoverage:
    """16e ölçümü: defterde başlamış fikstürün kaçı karar ve ölçüm aldı."""

    fixtures: int  # pencerede başlamış defter fikstürü
    decided: int  # bunlardan gölge satırı olan
    complete: int  # üç bileşeni tam
    settled: int  # tam ve sonuçlu
    closed: int  # tam ve kapanışı çözülen


@dataclass(frozen=True)
class ShadowReport:
    model_config_sha256: str
    decided: int  # gölge satırı olan maç
    incomplete: int  # bileşeni eksik: harmana girmez (fiyatı reddedilenler hariç)
    rejected_price: int  # yalnız piyasası yok, çünkü saklı `pre`yi donmuş yöntem reddeder (17g)
    settled: int  # tam ve sonuçlu
    unsettled: int  # tam ama tarihsel tabanda sonucu yok (henüz oynanmadı/senkronlanmadı, ad farkı)
    closed: int  # tam ve kapanışı çözülen
    bad_closing: int  # kapanış fiyatı var ama vig'i temizlenemedi (16i, sessiz değil)
    blend_log_loss: Interval | None
    market_log_loss: Interval | None
    blend_gap: Interval | None  # LL(harman) − LL(piyasa), aynı maçlarda eşleştirilmiş
    bet_clv: Interval | None
    bets: int
    tau: float
    fallback: tuple[str, ...]  # havuz ağırlığıyla harmanlanan ligler (satırı olanlar)
    leagues: Mapping[str, LeagueCoverage]


@dataclass(frozen=True)
class _Match:
    match_key: str
    league: str
    components: Mapping[str, tuple[float, float, float]]
    pre: tuple[float, float, float]


def _matches(predictions: Sequence[PredictionRow]) -> dict[str, _Match]:
    strays = sorted({row.strategy for row in predictions} - BASE_STRATEGIES)
    if strays:
        raise ValueError(f"mühür: gölge raporu baz dışı strateji aldı: {strays}")
    grouped: dict[str, list[PredictionRow]] = {}
    for row in predictions:
        grouped.setdefault(row.match_id, []).append(row)
    return {
        match_id: _Match(
            match_key=rows[0].match_key,
            league=rows[0].league,
            components=MappingProxyType({row.strategy: row.probs for row in rows}),
            pre=rows[0].pre,
        )
        for match_id, rows in grouped.items()
    }


def _rejected_price(match: _Match, method: str) -> bool:
    """17g: harmana YALNIZ piyasa bileşeni eksik diye girmeyen maçın eksiği fiyat reddi mi. Gölge
    piyasa satırını yalnız karar anı fiyatını devig reddedince yazmaz (`shadow.rejected_prices`);
    o fiyat öteki bileşenlerin satırında `pre` olarak saklıdır — yargı onunla yeniden kurulur."""
    missing = tuple(name for name in BLEND_COMPONENTS if name not in match.components)
    if missing != (MARKET,):
        return False
    try:
        devig(match.pre, method)
    except InvalidPrices:
        return True
    return False


def outcomes_of(history: Mapping[str, Sequence[HistMatch]]) -> Mapping[str, int]:
    """Gölge satırının `match_key`i → sonucun RESULTS sırası (0 ev, 1 beraberlik, 2 deplasman).
    Kaynak football-data tarihsel tabanıdır — gölge modelin kendi sonuç kaynağı (anahtarsız
    `load_matches`: DEV + POST, holdout yok). Anahtar maç kimliği DEĞİL, `match_key_text`."""
    return MappingProxyType(
        {
            match_key_text(record_of(match).key): RESULTS.index(match.result)
            for matches in history.values()
            for match in matches
            if match.result in RESULTS
        }
    )


def _interval(values: Sequence[float], resamples: int) -> Interval | None:
    return bootstrap_mean(values, resamples=resamples) if values else None


def _coverage(
    fixtures: Mapping[str, str],
    matches: Mapping[str, _Match],
    blends: Mapping[str, tuple[float, ...]],
    settled: frozenset[str],
    closings: Mapping[str, tuple[float, ...]],
) -> Mapping[str, LeagueCoverage]:
    leagues: dict[str, list[str]] = {}
    for match_id, league in fixtures.items():
        leagues.setdefault(league, []).append(match_id)
    return MappingProxyType(
        {
            league: LeagueCoverage(
                fixtures=len(ids),
                decided=sum(1 for i in ids if i in matches),
                complete=sum(1 for i in ids if i in blends),
                settled=sum(1 for i in ids if i in settled),
                closed=sum(1 for i in ids if i in blends and i in closings),
            )
            for league, ids in sorted(leagues.items())
        }
    )


def build_report(
    predictions: Sequence[PredictionRow],
    closing: Mapping[str, tuple[float, float, float]],
    outcomes: Mapping[str, int],
    weights: BlendWeights,
    *,
    tau: float,
    method: str,
    resamples: int,
    fixtures: Mapping[str, str] = MappingProxyType({}),
) -> ShadowReport:
    """Harman = donmuş ağırlıkla havuz; LL ve ΔLL tam + sonuçlu maçlarda, bahis CLV'si tam +
    kapanışlı maçlarda (§6.4 kuralı, `wf_eval.bet_clv`). `closing` ve `fixtures` maç kimliğiyle
    (`fixtures`: maç → lig kodu, 16e), `outcomes` ise gölge satırının `match_key`iyle anahtarlıdır
    (`outcomes_of`): maç kimliğiyle verilen sonuç eşleşmez, maç sonuçsuz sayılır."""
    matches = _matches(predictions)
    blends = {
        match_id: pool(
            [match.components[name] for name in BLEND_COMPONENTS],
            weights_for(weights, match.league),
        )
        for match_id, match in matches.items()
        if all(name in match.components for name in BLEND_COMPONENTS)
    }
    rejected = sum(1 for match in matches.values() if _rejected_price(match, method))
    closings: dict[str, tuple[float, ...]] = {}
    for match_id in blends:
        if match_id in closing:
            with contextlib.suppress(InvalidPrices):
                closings[match_id] = devig(closing[match_id], method)
    settled = sorted(match_id for match_id in blends if matches[match_id].match_key in outcomes)
    results = [outcomes[matches[match_id].match_key] for match_id in settled]
    blend_ll = per_match_log_loss([blends[i] for i in settled], results) if settled else ()
    market_ll = (
        per_match_log_loss([matches[i].components[MARKET] for i in settled], results)
        if settled
        else ()
    )
    clvs = [
        value
        for match_id in sorted(closings)
        if (value := bet_clv(blends[match_id], matches[match_id].pre, closings[match_id], tau))
        is not None
    ]
    return ShadowReport(
        model_config_sha256=weights.model_config_sha256,
        decided=len(matches),
        incomplete=len(matches) - len(blends) - rejected,
        rejected_price=rejected,
        settled=len(settled),
        unsettled=len(blends) - len(settled),
        closed=len(closings),
        bad_closing=sum(1 for match_id in blends if match_id in closing) - len(closings),
        blend_log_loss=_interval(blend_ll, resamples),
        market_log_loss=_interval(market_ll, resamples),
        blend_gap=_interval([b - m for b, m in zip(blend_ll, market_ll, strict=True)], resamples),
        bet_clv=_interval(clvs, resamples),
        bets=len(clvs),
        tau=tau,
        fallback=tuple(
            sorted({matches[i].league for i in blends if matches[i].league not in weights.leagues})
        ),
        leagues=_coverage(fixtures, matches, blends, frozenset(settled), closings),
    )


def render_report(report: ShadowReport, *, generated_at: datetime) -> str:
    """Toplu sayı; maç satırı yok. Yalnız baz serisi (market, elo_fit, dixon_coles → harman)."""
    fallback = ", ".join(report.fallback) or "yok"
    return "\n".join(
        [
            f"# Gölge CLV raporu — {generated_at.date().isoformat()}",
            "",
            f"Üretim: {generated_at.isoformat()} · `model_config_sha256` "
            f"`{report.model_config_sha256}` · harman donmuş ağırlıkla "
            "(`config/blend_weights_faz3.yaml`). Yalnız baz serisi okundu "
            f"({', '.join(sorted(BASE_STRATEGIES))}). "
            "Kapanış: mühürlü defter; sonuç: football-data tarihsel tabanı (haftalık senkron).",
            "",
            f"Karar verilen maç {report.decided} · bileşeni eksik {report.incomplete} · "
            f"fiyatı reddedilen {report.rejected_price} · "
            f"sonuçlu {report.settled} · sonuçsuz {report.unsettled} · "
            f"kapanışlı {report.closed} · "
            f"vig'i temizlenemeyen kapanış {report.bad_closing}",
            f"Havuz ağırlığıyla harmanlanan ligler: {fallback}",
            "",
            f"- LL harman: {format_interval(report.blend_log_loss)}",
            f"- LL piyasa: {format_interval(report.market_log_loss)}",
            f"- ΔLL harman − piyasa (eşleştirilmiş): {format_interval(report.blend_gap)}",
            f"- Bahis CLV (τ = {report.tau}): {format_interval(report.bet_clv)} · "
            f"bahis {report.bets}",
            "",
            "### Lig kapsamı (16e)",
            "",
            "| lig | fikstür | karar | tam | sonuçlu | kapanışlı |",
            "|---|---|---|---|---|---|",
            *(
                f"| {league} | {c.fixtures} | {c.decided} | {c.complete} | {c.settled} | "
                f"{c.closed} |"
                for league, c in report.leagues.items()
            ),
            "",
        ]
    )
