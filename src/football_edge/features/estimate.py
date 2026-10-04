"""Jev'siz maliyet ve takvim kuru koşusu (Plan 2 R184; I-10): `features estimate`.

YAZMAZ, Jev KURMAZ: salt okuma işlemi, sonunda geri alma. TR üretimde VARSAYILIR
(`ASSUMED_LANGUAGES`): kademe 1 çağrısı = son `WINDOW`da adayı olan (`candidate_fixtures`) haber;
kademe 2 ÜST SINIRI = gölge kararlarının, karar anından önceki `HORIZON`da takım adı geçen haberi
olan tarafları (kademe 1 kapısı henüz yok). Aylık dolar `config/faz4_ops.yaml` tahmin birimleriyle;
900'e varış geçerli kümenin sayacından ve haberli karar hızından. Kullanıcı durağı: aylık > 20 $ ya
da varış > 2027-06-30.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from football_edge.features.live_config import TIER1, TIER2, LiveConfig
from football_edge.features.slice import TARGET, eta_for
from football_edge.features.tier1 import HORIZON, candidate_fixtures, fold, team_tokens
from football_edge.features.tier2 import Decision
from football_edge.features.types import StoredNews
from football_edge.live.context import LiveMatch

WINDOW = timedelta(days=28)
ASSUMED_LANGUAGES = frozenset({"tr"})
STOP_MONTHLY_USD = 20.0
STOP_DATE = date(2027, 6, 30)
DAYS_PER_MONTH = 30.4


@dataclass(frozen=True)
class Estimate:
    tier1_calls: int
    tier2_sides: int
    news_decisions: int
    monthly_usd: float
    eta: date | None
    stops: tuple[str, ...]


def mentioned(team: str, item: StoredNews) -> bool:
    words = fold(f"{item.title} {item.body or ''}").split()
    return any(word.startswith(token) for token in team_tokens(team) for word in words)


def news_before(decision: Decision, items: Sequence[StoredNews]) -> tuple[StoredNews, ...]:
    start = decision.decided_at - HORIZON
    return tuple(
        item
        for item in items
        if item.lang in ASSUMED_LANGUAGES and start <= item.available_at < decision.decided_at
    )


def candidate_sides(decision: Decision, items: Sequence[StoredNews]) -> int:
    before = news_before(decision, items)
    teams = (decision.home, decision.away)
    return sum(1 for team in teams if any(mentioned(team, item) for item in before))


def stops_for(monthly_usd: float, eta: date | None) -> tuple[str, ...]:
    found: tuple[str, ...] = ()
    if monthly_usd > STOP_MONTHLY_USD:
        found = (*found, f"aylık tahmin ${monthly_usd:.2f} > ${STOP_MONTHLY_USD:.0f} (R184)")
    if eta is None or eta > STOP_DATE:
        found = (*found, f"{TARGET}'e varış {eta or 'tahmin yok'} > {STOP_DATE} (R184, R187)")
    return found


def estimate(
    items: Sequence[StoredNews],
    fixtures: Sequence[LiveMatch],
    decisions: Sequence[Decision],
    *,
    config: LiveConfig,
    slice_count: int,
    now: datetime,
) -> Estimate:
    recent = tuple(
        i for i in items if i.lang in ASSUMED_LANGUAGES and i.available_at >= now - WINDOW
    )
    tier1 = sum(1 for item in recent if candidate_fixtures(item, fixtures))
    sides = tuple(candidate_sides(decision, items) for decision in decisions)
    days = WINDOW / timedelta(days=1)
    daily = (tier1 * config.estimate_usd[TIER1] + sum(sides) * config.estimate_usd[TIER2]) / days
    monthly = DAYS_PER_MONTH * daily
    news_decisions = sum(1 for count in sides if count)
    weekly = news_decisions / (WINDOW / timedelta(weeks=1))
    eta = eta_for(slice_count, weekly, today=now.date())
    return Estimate(tier1, sum(sides), news_decisions, monthly, eta, stops_for(monthly, eta))


def render_estimate(found: Estimate) -> str:
    days, weeks = WINDOW.days, WINDOW.days / 7
    lines = [
        "kuru koşu (Jev'siz, TR üretimde varsayıldı — R184)",
        f"kademe 1 çağrı (son {days} gün): {found.tier1_calls} · "
        f"günlük {found.tier1_calls / days:.1f}",
        f"kademe 2 üst sınır taraf (son {days} gün): {found.tier2_sides}",
        f"haberli karar: {found.news_decisions} · haftalık {found.news_decisions / weeks:.1f}",
        f"aylık tahmin: ${found.monthly_usd:.2f} (tavan $25)",
        f"{TARGET}'e varış: {found.eta or 'tahmin yok'}",
        *(f"KULLANICI DURAĞI: {stop}" for stop in found.stops),
    ]
    return "\n".join(lines) + "\n"
