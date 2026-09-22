"""Lig başına piyasa verimliliği — yalnız geliştirme dönemi (tasarım §8, D12).

Holdout'a dokunmaz: önce `select_periods` yalnız DEV satırlarını bırakır, sonra pencere uygulanır.
İki katman bilerek ayrı: pencere bir gün yanlış yazılsa da holdout içeri giremez. Holdout
doluluğu (aday kuralı) satırlardan değil, kilitteki özetten okunur.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from types import MappingProxyType

import numpy as np

from football_edge.history.catalog import MAIN, HistoryLeague
from football_edge.history.holdout import (
    DEV,
    EXTRA_WINDOW,
    HOLDOUT,
    MAIN_WINDOW,
    Window,
    in_window,
    select_periods,
)
from football_edge.history.lock import HistoryLock
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, HistMatch
from football_edge.market.devig import DEFAULT_METHOD, METHODS, match_probs, overround
from football_edge.market.metrics import (
    Calibration,
    Interval,
    bootstrap_mean,
    brier,
    calibration,
    log_loss,
    outcome_index,
    per_match_log_loss,
    rps,
)

LOGGER = logging.getLogger("football_edge.market.efficiency")

AVERAGE = "Avg"  # (Avg, CLOSING) = AvgC, referans kapanış (D3); (Avg, PRE_CLOSING) = Avg
BEST = "Max"  # (Max, PRE_CLOSING): kapanış öncesi en iyi fiyat
SHARP = "PS"  # (PS, CLOSING) = PSC: keskin kitabın kapanışı
EXCHANGE = "BFE"  # (BFE, CLOSING) = BFEC: Betfair borsası kapanışı (D3 "varsa raporlanır", R97)
SHARP_COVERAGE = 0.90  # PSC/BFEC farkı: AvgC ile birlikte lig-sezonda doluluk alt sınırı
MIN_MATCHES = 1000  # aday: geliştirme N alt sınırı (tasarım §8.4)
MIN_HOLDOUT_COVERAGE = 0.95  # aday: kilitteki holdout AvgC doluluğu alt sınırı
RESAMPLES = 2000
SEED = 20260922
LEVEL = 0.95


@dataclass(frozen=True)
class LeagueEfficiency:
    code: str
    league_id: str
    kind: str
    n: int
    margin: Interval
    log_loss: Interval
    brier: float
    rps: float
    calibration: Calibration
    slope: Interval
    late_info: Interval | None
    value_rate: Interval | None
    sharp_gap: Interval | None
    ou25_margin: Interval | None
    ou25_log_loss: Interval | None
    ou25_calibration: Calibration | None
    exchange_gap: Interval | None


@dataclass(frozen=True)
class Ranking:
    late_info: tuple[str, ...]
    miscalibration: tuple[str, ...]
    tiers: Mapping[str, str]


class Unmeasurable(ValueError):
    """Lig ölçülemez: rapor onu DÜŞÜRMEZ, satırını `n` ve "—" hücreleriyle yazar (R100, R114)."""

    def __init__(self, message: str, *, n: int = 0) -> None:
        super().__init__(message)
        self.n = n  # geliştirme penceresinde AvgC 1X2'si tam maç sayısı


class NoClosingPrices(Unmeasurable):
    """Ligin geliştirme penceresinde AvgC 1X2'si tam tek maç yok: ölçülemez, rapor onu "—" yazar."""


@dataclass(frozen=True)
class _Sample:
    """Aynı sırada hizalanmış maçlar, fiyatlar, adil olasılıklar ve gerçekleşen sonuç sıraları."""

    matches: tuple[HistMatch, ...]
    prices: tuple[tuple[float, ...], ...]
    probs: tuple[tuple[float, ...], ...]
    outcomes: tuple[int, ...]


def _window(league: HistoryLeague) -> Window:
    return MAIN_WINDOW if league.kind == MAIN else EXTRA_WINDOW


def _development_rows(league: HistoryLeague, matches: Sequence[HistMatch]) -> tuple[HistMatch, ...]:
    development = select_periods(matches, periods=frozenset({DEV}))
    window = _window(league)
    # `in_window` bu modülün adıyla çağrılır: sızıntı testi onu yamalayıp (R89 holdout'a uzanan
    # pencereyi yasaklar) holdout'u yalnız dönem süzgecinin durdurduğunu kanıtlar.
    return tuple(match for match in development if in_window(match, window))


def _closing(match: HistMatch, book: str, method: str) -> tuple[float, ...] | None:
    return match_probs(match, book=book, market=H2H, phase=CLOSING, method=method)


def _sample(
    matches: Sequence[HistMatch], *, book: str, market: str, phase: str, method: str
) -> _Sample:
    rows = [
        (match, prices, probs, outcome_index(match, market))
        for match in matches
        if (prices := match.prices(book, market, phase)) is not None
        and (probs := match_probs(match, book=book, market=market, phase=phase, method=method))
        is not None
    ]
    return _Sample(
        matches=tuple(row[0] for row in rows),
        prices=tuple(row[1] for row in rows),
        probs=tuple(row[2] for row in rows),
        outcomes=tuple(row[3] for row in rows),
    )


def _fit(
    probs: Sequence[Sequence[float]], outcomes: Sequence[int], *, code: str, n: int
) -> Calibration:
    """Kalibrasyon fiti; ayrışırsa (çok az maç, ayrışan örnek) lig ölçülemez (R114, R115).

    YALNIZ fit çevrilir: satırlar buraya gelmeden girdiyi doğrulayan ölçütlerden geçmiştir, bozuk
    girdi ya da geçersiz tekrar sayısı düz `ValueError` olarak yükselir.
    """
    try:
        return calibration(probs, outcomes)
    except ValueError as failure:
        raise Unmeasurable(
            f"{code}: {n} maçla kalibrasyon kurulamadı — {failure}", n=n
        ) from failure


def _slope_interval(close: _Sample, estimate: float, *, resamples: int, code: str) -> Interval:
    """Eğimin yüzdelik aralığı: maçlar yeniden örneklenir, fit her örnekte YENİDEN kurulur."""
    rng = np.random.default_rng(SEED)
    size = len(close.matches)
    slopes = []
    for _ in range(resamples):
        picked = rng.integers(0, size, size=size)
        probs = [close.probs[index] for index in picked]
        outcomes = [close.outcomes[index] for index in picked]
        slopes.append(_fit(probs, outcomes, code=code, n=size).slope)
    tail = (1.0 - LEVEL) / 2.0 * 100.0
    low, high = np.percentile(slopes, [tail, 100.0 - tail])
    return Interval(estimate=estimate, low=float(low), high=float(high))


def _late_info(close: _Sample, *, method: str, resamples: int) -> Interval | None:
    """Maç başına LL(kapanış öncesi Avg) − LL(AvgC): büyükse bilgi kapanıştan önce gelmiyor."""
    rows = [
        (early, late, outcome)
        for match, late, outcome in zip(close.matches, close.probs, close.outcomes, strict=True)
        if (early := match_probs(match, book=AVERAGE, market=H2H, phase=PRE_CLOSING, method=method))
        is not None
    ]
    if not rows:
        return None
    outcomes = [row[2] for row in rows]
    early_loss = per_match_log_loss([row[0] for row in rows], outcomes)
    late_loss = per_match_log_loss([row[1] for row in rows], outcomes)
    gaps = [early - late for early, late in zip(early_loss, late_loss, strict=True)]
    return bootstrap_mean(gaps, resamples=resamples)


def _value_rate(close: _Sample, *, resamples: int) -> Interval | None:
    """max_i(Max_i · p_kapanış_i) > 1 olan maçların payı — geriye dönük üst sınır."""
    hits = [
        1.0 if max(price * fair for price, fair in zip(best, probs, strict=True)) > 1.0 else 0.0
        for match, probs in zip(close.matches, close.probs, strict=True)
        if (best := match.prices(BEST, H2H, PRE_CLOSING)) is not None
    ]
    return bootstrap_mean(hits, resamples=resamples) if hits else None


def _book_gap(
    rows: Sequence[HistMatch], *, book: str, method: str, resamples: int
) -> Interval | None:
    """LL(AvgC) − LL(`book` kapanışı), yalnız ikisinin birlikte ≥ %90 dolu olduğu lig-sezonlarda."""
    gaps: list[float] = []
    for season in sorted({match.season for match in rows}):
        members = [match for match in rows if match.season == season]
        both = [
            (average, other, outcome_index(match, H2H))
            for match in members
            if (average := _closing(match, AVERAGE, method)) is not None
            and (other := _closing(match, book, method)) is not None
        ]
        if len(both) / len(members) < SHARP_COVERAGE:
            continue
        outcomes = [row[2] for row in both]
        average_loss = per_match_log_loss([row[0] for row in both], outcomes)
        other_loss = per_match_log_loss([row[1] for row in both], outcomes)
        gaps.extend(a - o for a, o in zip(average_loss, other_loss, strict=True))
    return bootstrap_mean(gaps, resamples=resamples) if gaps else None


def _totals(
    rows: Sequence[HistMatch], *, method: str, resamples: int, code: str
) -> tuple[Interval | None, Interval | None, Calibration | None]:
    """Ü/A 2.5 kapanışı (AvgC>2.5, AvgC<2.5): marj, log loss, kalibrasyon.

    Tam satır yoksa ya da Ü/A fiti ayrışırsa üçü de None ("—"): lig 1X2 ölçütleri ve adaylığıyla
    kalır (R116; adaylar 1X2'den seçilir, R92 bu alanları Optional tanımlar).
    """
    sample = _sample(rows, book=AVERAGE, market=TOTALS_25, phase=CLOSING, method=method)
    if not sample.matches:
        return None, None, None
    # Girdiyi doğrulayan ölçütler yakalamanın dışında (R115): bozuk girdi düz hata olarak yükselir.
    margin = bootstrap_mean([overround(prices) for prices in sample.prices], resamples=resamples)
    loss = bootstrap_mean(per_match_log_loss(sample.probs, sample.outcomes), resamples=resamples)
    try:
        fit = calibration(sample.probs, sample.outcomes)
    except ValueError:
        LOGGER.warning(
            "lig=%s Ü/A 2.5 kalibrasyonu %d maçla kurulamadı — Ü/A 2.5 ölçütleri boş bırakıldı",
            code,
            len(sample.matches),
        )
        return None, None, None
    return margin, loss, fit


def league_efficiency(
    league: HistoryLeague, matches: Sequence[HistMatch], *, method: str, resamples: int = RESAMPLES
) -> LeagueEfficiency:
    """Tasarım §8.2'nin ölçütleri; N = geliştirme penceresinde AvgC 1X2'si tam maçlar."""
    rows = _development_rows(league, matches)
    close = _sample(rows, book=AVERAGE, market=H2H, phase=CLOSING, method=method)
    if not close.matches:
        raise NoClosingPrices(f"{league.code}: geliştirme penceresinde AvgC 1X2'si tam maç yok")
    return _measured(league, rows, close, method=method, resamples=resamples)


def _measured(
    league: HistoryLeague,
    rows: tuple[HistMatch, ...],
    close: _Sample,
    *,
    method: str,
    resamples: int,
) -> LeagueEfficiency:
    main = league.kind == MAIN
    n = len(close.matches)  # AvgC 1X2'si tam maçlar — penceredeki bütün satırlar değil
    # Girdiyi doğrulayan ölçütler fit'ten ÖNCE ve hiçbir yakalamanın dışında (R115): bozuk olasılık
    # satırı ya da tekrar sayısı < 1 düz `ValueError`dır; "ölçülemez"e yalnız `_fit` çevirir.
    margin = bootstrap_mean([overround(prices) for prices in close.prices], resamples=resamples)
    loss = bootstrap_mean(per_match_log_loss(close.probs, close.outcomes), resamples=resamples)
    brier_score, rps_score = brier(close.probs, close.outcomes), rps(close.probs, close.outcomes)
    fit = _fit(close.probs, close.outcomes, code=league.code, n=n)
    ou25_margin, ou25_loss, ou25_fit = (
        _totals(rows, method=method, resamples=resamples, code=league.code)
        if main
        else (None, None, None)
    )
    return LeagueEfficiency(
        code=league.code,
        league_id=league.league_id,
        kind=league.kind,
        n=n,
        margin=margin,
        log_loss=loss,
        brier=brier_score,
        rps=rps_score,
        calibration=fit,
        slope=_slope_interval(close, fit.slope, resamples=resamples, code=league.code),
        late_info=_late_info(close, method=method, resamples=resamples) if main else None,
        value_rate=_value_rate(close, resamples=resamples) if main else None,
        sharp_gap=_book_gap(rows, book=SHARP, method=method, resamples=resamples),
        ou25_margin=ou25_margin,
        ou25_log_loss=ou25_loss,
        ou25_calibration=ou25_fit,
        exchange_gap=_book_gap(rows, book=EXCHANGE, method=method, resamples=resamples),
    )


def _every_method(match: HistMatch) -> tuple[tuple[float, ...], ...] | None:
    found: list[tuple[float, ...]] = []
    for method in METHODS:
        probs = _closing(match, AVERAGE, method)
        if probs is None:
            return None
        found.append(probs)
    return tuple(found)


def method_scores(matches: Sequence[HistMatch]) -> Mapping[str, float]:
    """Yöntem → havuzlanmış AvgC log loss'u; her yöntemin çözdüğü ORTAK geliştirme maçlarında."""
    table = [
        (probs, outcome_index(match, H2H))
        for match in select_periods(matches, periods=frozenset({DEV}))
        if (probs := _every_method(match)) is not None
    ]
    if not table:
        raise ValueError("geliştirme döneminde her yöntemin çözebildiği AvgC maçı yok")
    outcomes = [outcome for _, outcome in table]
    scores = {
        method: log_loss([probs[index] for probs, _ in table], outcomes)
        for index, method in enumerate(METHODS)
    }
    return MappingProxyType(scores)


def best_method(scores: Mapping[str, float]) -> str:
    """En düşük havuzlanmış log loss'lu yöntem; eşitlikte ada göre (tasarım §6)."""
    return min(scores, key=lambda method: (scores[method], method))


def _distance(slope: Interval) -> Interval:
    """|b − 1| ve aralığı: eğim aralığı 1'i içeriyorsa uzaklığın alt ucu 0'dır."""
    estimate = abs(slope.estimate - 1.0)
    if slope.low > 1.0:
        return Interval(estimate, slope.low - 1.0, slope.high - 1.0)
    if slope.high < 1.0:
        return Interval(estimate, 1.0 - slope.high, 1.0 - slope.low)
    return Interval(estimate, 0.0, max(1.0 - slope.low, slope.high - 1.0))


def _tiers(intervals: Mapping[str, Interval]) -> dict[str, str]:
    """Aralık medyanın açıkça üstündeyse A, açıkça altındaysa C, medyanı içeriyorsa B."""
    if not intervals:
        return {}
    middle = median(interval.estimate for interval in intervals.values())
    return {
        code: "A" if interval.low > middle else ("C" if interval.high < middle else "B")
        for code, interval in intervals.items()
    }


def rank(rows: Sequence[LeagueEfficiency]) -> Ranking:
    """R1 geç bilgi (ana ligler) ve R2 kalibrasyon hatası; bileşik puan YOK (tasarım §8.3)."""
    late = {row.code: row.late_info for row in rows if row.late_info is not None}
    distance = {row.code: _distance(row.slope) for row in rows}
    ece = {row.code: row.calibration.ece for row in rows}
    late_order = sorted(late, key=lambda code: (-late[code].estimate, code))
    miss_order = sorted(distance, key=lambda code: (-distance[code].estimate, -ece[code], code))
    late_tiers, miss_tiers = _tiers(late), _tiers(distance)
    # Ligin kademesi iki sıralamadaki İYİSİDİR: "A" < "B" < "C".
    tiers = {code: min(tier, late_tiers.get(code, "C")) for code, tier in miss_tiers.items()}
    return Ranking(tuple(late_order), tuple(miss_order), MappingProxyType(tiers))


def _holdout_coverage(lock: HistoryLock, code: str) -> float:
    """Holdout satırı OKUNMAZ: doluluk kilitteki özetten gelir (avgc_complete / rows)."""
    periods = lock.leagues.get(code)
    if periods is None or HOLDOUT not in periods:
        raise ValueError(f"{code}: kilitte holdout özeti yok")
    digest = periods[HOLDOUT]
    return digest.avgc_complete / digest.rows if digest.rows else 0.0


def _odds_api_key(leagues: Sequence[HistoryLeague], code: str) -> str:
    for league in leagues:
        if league.code == code:
            return league.odds_api_key
    raise ValueError(f"{code}: lig kataloğunda yok")


def candidates(
    rows: Sequence[LeagueEfficiency],
    ranking: Ranking,
    *,
    lock: HistoryLock,
    leagues: Sequence[HistoryLeague],
) -> tuple[str, ...]:
    """Tasarım §8.4: N ≥ 1000 · holdout AvgC ≥ %95 · Odds API anahtarı · R1/R2'de A ya da B."""
    chosen = [
        row.code
        for row in rows
        if row.n >= MIN_MATCHES
        and _holdout_coverage(lock, row.code) >= MIN_HOLDOUT_COVERAGE
        and _odds_api_key(leagues, row.code) != ""
        and ranking.tiers.get(row.code) in ("A", "B")
    ]
    return tuple(sorted(chosen, key=lambda code: (ranking.tiers[code], code)))


# ── Rapor: yalnız toplu sayılar; ham satır, takım adı, tarih YOK (spec §3.2/4) ──────────────

_HEADER = (
    "| Lig | Kimlik | Tür | N | Marj | Log loss | Brier | RPS | Eğim b | Kesişim a | ECE "
    "| Geç bilgi ΔLL | Değer sıklığı* | Keskinlik farkı (PSC) | Borsa farkı (BFEC) "
    "| Ü/A 2.5 marj | Ü/A 2.5 LL | Ü/A 2.5 eğim |"
)
_VALUE_NOTE = (
    "\\* Değer sıklığı GERİYE DÖNÜK ÜST SINIRDIR, ulaşılabilir değildir: adil kapanış olasılığı "
    "ancak maç başlarken bilinir (tasarım §8.2)."
)
# Tasarım §13'ün 3, 4, 5 ve 9. maddeleri — bu raporun ölçmedikleri.
_NOT_MEASURED = (
    "- **2019/20 öncesi ana lig satırlarında saat yok**: gün içi sıralama o dönemde yaklaşık "
    "(tutucu kural).",
    "- **`AvgC`'nin kitap kümesi zamanla değişiyor** ve satır başına yayımlanmıyor: referans "
    "sezonlar arası sabit bir büyüklük değildir.",
    "- **Holdout'ta `PSC` kullanılamaz** (%23–55, bayat); `BFEC` yalnız 2024/25'ten.",
    "- **Bootstrap maçları bağımsız sayar**; aynı haftanın maçları arasındaki ortak şoklar "
    "aralıkları olduğundan dar gösterebilir.",
)


_NO_COUNTS: Mapping[str, int] = MappingProxyType({})


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def _interval(interval: Interval | None) -> str:
    if interval is None:
        return "—"
    return f"{interval.estimate:.4f} [{interval.low:.4f}, {interval.high:.4f}]"


def _window_text(window: Window) -> str:
    start = "—" if window.start is None else window.start.isoformat()
    return f"[{start}, {window.end.isoformat()})"


def _score_lines(scores: Mapping[str, float]) -> list[str]:
    chosen = best_method(scores)
    lines = [
        "## Vig yöntemleri (K2)",
        "",
        "Havuzlanmış kapanış (`AvgC`) log loss'u, her yöntemin çözebildiği ortak maçlarda.",
        "",
        "| Yöntem | Log loss |",
        "|---|---|",
        *(f"| {method} | {score:.5f} |" for method, score in scores.items()),
        "",
        f"Seçilen yöntem: **{chosen}** (lig tablosu bununla) · `DEFAULT_METHOD`: {DEFAULT_METHOD}",
    ]
    if chosen != DEFAULT_METHOD:
        lines.append(f"UYARI: ölçüm `{chosen}` seçti; `DEFAULT_METHOD` Task 12'de güncellenmeli.")
    return [*lines, ""]


def _league_line(row: LeagueEfficiency) -> str:
    ou25_slope = None if row.ou25_calibration is None else row.ou25_calibration.slope
    cells = (
        row.code,
        row.league_id,
        row.kind,
        str(row.n),
        _interval(row.margin),
        _interval(row.log_loss),
        _number(row.brier),
        _number(row.rps),
        _interval(row.slope),
        _number(row.calibration.intercept),
        _number(row.calibration.ece),
        _interval(row.late_info),
        _interval(row.value_rate),
        _interval(row.sharp_gap),
        _interval(row.exchange_gap),
        _interval(row.ou25_margin),
        _interval(row.ou25_log_loss),
        _number(ou25_slope),
    )
    return "| " + " | ".join(cells) + " |"


def _unmeasured_line(league: HistoryLeague, n: int) -> str:
    # Ölçülemeyen lig tablodan DÜŞMEZ: N'si ve her ölçüt "—" (kısmî kayıp sessiz geçmez).
    metrics = _HEADER.count("|") - 1 - 4
    return (
        "| "
        + " | ".join((league.code, league.league_id, league.kind, str(n), *("—",) * metrics))
        + " |"
    )


def _ranking_lines(ranking: Ranking) -> list[str]:
    def listed(codes: tuple[str, ...]) -> list[str]:
        numbered = [
            f"{place}. {code} — kademe {ranking.tiers[code]}" for place, code in enumerate(codes, 1)
        ]
        return numbered or ["(lig yok)"]

    return [
        "## Sıralamalar",
        "",
        "Bileşik puan yok (tasarım §8.3). Kademe: aralığın alt ucu medyanın üstündeyse A, üst ucu "
        "altındaysa C, yoksa B; ligin kademesi iki sıralamadaki iyisidir.",
        "",
        "### R1 — geç bilgi (ΔLL, ana ligler, büyükten küçüğe)",
        "",
        *listed(ranking.late_info),
        "",
        "### R2 — kapanış kalibrasyon hatası (|b − 1|, eşitlikte ECE)",
        "",
        *listed(ranking.miscalibration),
        "",
    ]


def render_report(
    rows: Sequence[LeagueEfficiency],
    ranking: Ranking,
    *,
    scores: Mapping[str, float],
    candidates: Sequence[str],
    generated_at: datetime,
    unmeasured: Sequence[HistoryLeague] = (),
    unmeasured_counts: Mapping[str, int] = _NO_COUNTS,
) -> str:
    """Markdown rapor: yöntem puanları, lig tablosu, iki sıralama, adaylar, ölçülmeyenler.

    `unmeasured`: ölçülemeyen ligler (`Unmeasurable`) — satırları "—" ile; N'leri
    `unmeasured_counts`tan (yoksa 0: AvgC 1X2'si tam maç yok, `NoClosingPrices`).
    """
    lines = [
        "# Piyasa verimliliği — geliştirme dönemi",
        "",
        f"Üretildi: {generated_at.isoformat()} · Pencere: ana ligler {_window_text(MAIN_WINDOW)}, "
        f"ek ligler {_window_text(EXTRA_WINDOW)} · holdout satırı ölçüme girmedi "
        "(doluluk kilitteki özetten).",
        "",
        "Aralıklar %95 yüzdelik bootstrap (maç düzeyinde, sabit tohum). Yalnız toplu sayılar.",
        "",
        *_score_lines(scores),
        "## Lig başına ölçütler",
        "",
        _HEADER,
        "|" + "---|" * (_HEADER.count("|") - 1),
        *(_league_line(row) for row in rows),
        *(_unmeasured_line(league, unmeasured_counts.get(league.code, 0)) for league in unmeasured),
        "",
        _VALUE_NOTE,
        "",
        *_ranking_lines(ranking),
        "## Aday ligler",
        "",
        "Ölçüt (tasarım §8.4): geliştirme N ≥ 1000 · holdout `AvgC` doluluğu ≥ %95 (kilitten) · "
        "The Odds API anahtarı var · R1 ya da R2'de A veya B kademesi.",
        "",
        *([f"- {code}" for code in candidates] or ["Aday lig yok."]),
        "",
        "## Raporun ölçmedikleri",
        "",
        *_NOT_MEASURED,
    ]
    return "\n".join(lines) + "\n"
