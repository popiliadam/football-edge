"""Tek gerçek çağrı ölçümü (Plan 2 R184; Task 5): `features probe --tier {1,2}`.

Bir kademe 1 ya da bir kademe 2 bataryası sorar; gecikmeyi ve DÖNEN model adını basar. CEVAP
TABLOLARINA YAZMAZ (M-8): veri bağlantısı salt okumadır; harcama `jev_spend`e her çağrı gibi
yazılır. Ölçüm TR kalibrasyonundan ÖNCE yapılır: dil `estimate.ASSUMED_LANGUAGES` (R178'in bilinçli
istisnası — cevap hiçbir tabloya ve özelliğe girmez).

Ölçülemeyen probe `ProbeFailure` döner ve sebebini adıyla taşır (son inceleme I2): sorulacak haber
yok (`PROBE_NO_NEWS`, Jev çağrılmadı), çağrı denendi ama Jev/yetki hatasıyla düştü
(`PROBE_JEV_ERROR`) ya da aylık tavan çağrıyı durdurdu (`PROBE_BUDGET`). Gerçek bir Jev arızası
"haber yok" diye okunmaz.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from football_edge.features.derive import item_set_hash
from football_edge.features.estimate import mentioned, news_before
from football_edge.features.questions import QuestionSet
from football_edge.features.tier1 import run_tier1
from football_edge.features.tier2 import Decision, SideTask, side_battery, side_state
from football_edge.features.types import AWAY, HOME, StoredNews
from football_edge.jev import BatteryAnswer, ChoiceAnswer, JevClient, Question
from football_edge.jev_budget import BudgetExceeded
from football_edge.live.context import LiveMatch

LOGGER = logging.getLogger("football_edge.features.probe")

PROBE_ITEMS = 5
PROBE_NO_NEWS = "no_news"  # sorulacak haber yok: Jev çağrılmadı
PROBE_JEV_ERROR = "jev_error"  # çağrı denendi, Jev/yetki hatasıyla düştü
PROBE_BUDGET = "budget"  # aylık tavan çağrıyı durdurdu


@dataclass(frozen=True)
class ProbeFailure:
    tier: str
    reason: str
    detail: str = ""  # Jev hatasının sebebi (`jev_error:<tür>`)


@dataclass(frozen=True)
class ProbeResult:
    tier: str
    seconds: float
    jev_model: str
    answered: int
    asked: int


class TimingJev:
    """Sarılan istemcinin her bataryasının süresini ve dönen modelini kaydeder (kendi kaydı)."""

    def __init__(self, inner: JevClient, timer: Callable[[], float] = time.perf_counter) -> None:
        self._inner = inner
        self._timer = timer
        self.timings: tuple[tuple[float, str], ...] = ()

    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer:
        return self._inner.ask_choice(state, instructions, criteria)

    def ask_battery(self, state: Mapping[str, Any], questions: Sequence[Question]) -> BatteryAnswer:
        start = self._timer()
        answer = self._inner.ask_battery(state, questions)
        self.timings = (*self.timings, (self._timer() - start, answer.jev_model))
        return answer


def probe_tier1(
    items: Sequence[StoredNews],
    fixtures: Sequence[LiveMatch],
    client: JevClient,
    questions: QuestionSet,
    *,
    clock: Callable[[], datetime],
) -> ProbeResult | ProbeFailure:
    timing = TimingJev(client)
    run = run_tier1(items, timing, questions, fixtures=fixtures, clock=clock, max_calls=1)
    if not timing.timings:
        if run.budget_hit:
            return ProbeFailure("kademe 1", PROBE_BUDGET)
        if run.calls:
            # Tek çağrı (`max_calls=1`) zamanlanmadıysa Jev hatasıyla düştü: sebebi işaretinde.
            reasons = (marker.choice for marker in (*run.pending, *run.failures))
            return ProbeFailure("kademe 1", PROBE_JEV_ERROR, next(reasons, ""))
        return ProbeFailure("kademe 1", PROBE_NO_NEWS)
    seconds, model = timing.timings[0]
    return ProbeResult("kademe 1", seconds, model, len(run.rows), run.asked)


def probe_task(decisions: Sequence[Decision], items: Sequence[StoredNews]) -> SideTask | None:
    """En yeni kararın, adı haberde geçen ilk tarafı; son `PROBE_ITEMS` haberle."""
    for decision in sorted(decisions, key=lambda d: d.decided_at, reverse=True):
        before = news_before(decision, items)
        for side, team in ((HOME, decision.home), (AWAY, decision.away)):
            news = tuple(item for item in before if mentioned(team, item))[-PROBE_ITEMS:]
            if news:
                return SideTask(decision, side, team, news, item_set_hash(news))
    return None


def probe_tier2(
    task: SideTask, client: JevClient, questions: QuestionSet
) -> ProbeResult | ProbeFailure:
    timing = TimingJev(client)
    battery = side_battery(questions, side=task.side, team=task.team)
    try:
        answer = timing.ask_battery(side_state(task), battery)
    except BudgetExceeded:
        return ProbeFailure("kademe 2", PROBE_BUDGET)
    except Exception as error:
        LOGGER.exception("jev: probe kademe 2 sorulamadı")
        return ProbeFailure("kademe 2", PROBE_JEV_ERROR, f"jev_error:{type(error).__name__}")
    seconds, model = timing.timings[0]
    return ProbeResult("kademe 2", seconds, model, len(answer.answers), len(battery))
