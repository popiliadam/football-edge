"""Kademe 2: karar anında taraf başına batarya (Plan 2 R180, R185; spec §5/1, §6).

Maç kümesi bu turun GÖLGE satırlarıdır: `model_predictions`te `(match_id, decided_at)` VARLIĞI
okunur, olasılık okunmaz (I-2, M-1). Haber kümesi `derive.select_items` (`available_at <
decided_at`; canlıda kademe 1 `asked_at < decided_at`); kademe 1 kapıları yalnız karardan ÖNCE
sorulmuş cevaplardan kurulur (I-3, `gates_as_of`). Taraf kümesi ev = ev ∪ ikisi, deplasman =
deplasman ∪ ikisi; `item_set_hash` taraf başına (M-4). Taraf başına TEK batarya: T2 + T3 + T4 (30
soru), kimlik `<soru>:<taraf>`. Haberi olmayan taraf SORULMAZ — özellikte "yok" atanır
(`derive.side_answers`, I-1). Yalnız `variant = real` (kanarya arşiv içindi, R167).

Taraf durumu (inceleme I5): her gölge (maç, karar anı, taraf) için sonuç bir İŞARET satırıdır
— `question_id = side_status:<taraf>:<sonuç>`, `choice` = sonuç (`OUTCOMES`), olasılık
`{sonuç: 1}`, maliyet 0 (tier1'in `t1_failed:<n>` deseni). Plan 3 karar anındaki dil kümesini ve
"yok" atamasını (`no_news`) yeniden kurmaz, buradan okur; özellik okuyucusu `STATUS_PREFIX`i süzer.
Bir tarafın birden çok işareti olabilir (önce `budget`, sonra `asked`); geçerli sonuç
`final_status` önceliğidir. Cevaplanmış taraf = `asked` işareti (M-3).

Korumalar: karardan `max_decision_age` (6 sa) sonra sormaz (M-2); dönen model kümedekinden farklıysa
YAZMAZ, durur (R185); tur başına taraf tavanı, taraf başına `sink` (CLI'da yaz + commit, I-8); art
arda `OUTAGE_STREAK` Jev hatası kesintidir.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any

import psycopg

from football_edge.features.derive import item_set_hash, select_items
from football_edge.features.live_config import LiveConfig
from football_edge.features.news import load_news
from football_edge.features.questions import QuestionSet, for_team
from football_edge.features.tier1 import (
    CLUSTER_WINDOW,
    FAILED_PREFIX,
    HORIZON,
    NO_MODEL,
    OUTAGE_STREAK,
    ItemAnswerRow,
    gates_from,
)
from football_edge.features.types import AWAY, BOTH, HOME, ItemGate, StoredNews
from football_edge.jev import BatteryAnswer, ChoiceAnswer, JevClient, Question
from football_edge.jev_budget import BudgetExceeded

LOGGER = logging.getLogger("football_edge.features.tier2")

# Gölge raporunun baz stratejileri (`live.store.BASE_STRATEGIES`): o modül `features/`ten import
# edilemez (spec §5/4) — eşitliği `tests/test_feature_tier2.py` sabitler.
SHADOW_STRATEGIES: tuple[str, ...] = ("dixon_coles", "elo_fit", "market")
VARIANT_REAL = "real"
# Haber penceresi karar anına göre sabit: kademe 1 ufku + küme penceresi (yeniden üretilebilir).
ITEM_LOOKBACK = HORIZON + CLUSTER_WINDOW
_MEMBERS: Mapping[str, frozenset[str]] = MappingProxyType(
    {HOME: frozenset({HOME, BOTH}), AWAY: frozenset({AWAY, BOTH})}
)
_SIDE_ORDER = (HOME, AWAY)

# Taraf sonuçları — öncelik sırasıyla (`final_status`). `ANSWERED_BEFORE` sayılır, işaretlenmez.
ASKED = "asked"
NO_NEWS = "no_news"
STALE = "stale"
DEFERRED = "deferred"
ERROR = "error"
BUDGET = "budget"
OUTAGE = "outage"
MODEL_DRIFT = "model_drift"
OUTCOMES = (ASKED, NO_NEWS, STALE, DEFERRED, ERROR, BUDGET, OUTAGE, MODEL_DRIFT)
ANSWERED_BEFORE = "answered_before"
STATUS_PREFIX = "side_status:"


def status_question(side: str, outcome: str) -> str:
    if side not in _SIDE_ORDER or outcome not in OUTCOMES:
        raise ValueError(f"bilinmeyen taraf ya da sonuç: {side!r}, {outcome!r}")
    return f"{STATUS_PREFIX}{side}:{outcome}"


def is_status(question_id: str) -> bool:
    """İşaret satırı cevap değildir: özellik okuyucusu bunu süzer (Plan 3)."""
    return question_id.startswith(STATUS_PREFIX)


# Cevaplanmış taraf (M-3) ve seçim dilimi (R181) yalnız bu işaretlere bakar.
ASKED_MARKERS: tuple[str, ...] = tuple(status_question(side, ASKED) for side in _SIDE_ORDER)


def final_status(outcomes: Iterable[str]) -> str:
    """Bir tarafın geçerli sonucu: `OUTCOMES` sırasında ilk görülen (`asked` her şeyi ezer)."""
    found = set(outcomes)
    return next(outcome for outcome in OUTCOMES if outcome in found)


@dataclass(frozen=True)
class Decision:
    match_id: str
    decided_at: datetime
    home: str
    away: str
    kickoff: datetime


@dataclass(frozen=True)
class SideTask:
    decision: Decision
    side: str
    team: str
    items: tuple[StoredNews, ...]
    item_set_hash: str

    @property
    def key(self) -> tuple[str, datetime, str]:
        return self.decision.match_id, self.decision.decided_at, self.side


@dataclass(frozen=True)
class MatchAnswerRow:
    match_id: str
    decided_at: datetime
    prompt_version: str
    question_id: str
    variant: str
    item_set_hash: str
    choice: str
    probabilities: Mapping[str, float]
    confidence: float
    jev_model: str
    asked_at: datetime
    cost_usd: float


@dataclass(frozen=True)
class Tier2Run:
    rows: tuple[MatchAnswerRow, ...]  # cevaplar + durum işaretleri
    outcomes: Mapping[str, int]  # sonuç → taraf sayısı (`ANSWERED_BEFORE` dâhil)
    failed: int  # cevapsız ya da geçersiz soru
    stop: str | None = None  # BUDGET | OUTAGE | MODEL_DRIFT: kalan taraflar sorulmadı
    model_drift: str | None = None  # dönen model (cevabı yazılmadı)

    def count(self, outcome: str) -> int:
        return self.outcomes.get(outcome, 0)

    @property
    def asked_sides(self) -> int:
        return self.count(ASKED)

    @property
    def budget_hit(self) -> bool:
        return self.stop == BUDGET

    @property
    def outage(self) -> bool:
        return self.stop == OUTAGE


# ── Küme ───────────────────────────────────────────────────────────────────────────────────


def gates_as_of(rows: Sequence[ItemAnswerRow], decided_at: datetime) -> Mapping[int, ItemGate]:
    """Kademe 1 kapıları yalnız karardan ÖNCE sorulmuş cevaplardan (I-3): sonra sorulan cevap ne
    kapıyı ne kümelemeyi etkiler. Tam eşit an DIŞARIDADIR (`derive` modül belgesi)."""
    if decided_at.tzinfo is None:
        raise ValueError("decided_at saat dilimsiz")
    return gates_from([row for row in rows if row.asked_at < decided_at])


def side_tasks(
    decision: Decision,
    items: Sequence[StoredNews],
    item_rows: Sequence[ItemAnswerRow],
    *,
    config: LiveConfig,
    languages: frozenset[str],
) -> tuple[SideTask, ...]:
    """Kararın İKİ tarafı; haberi olmayan tarafın kümesi boştur (sorulmaz, `no_news`, I-1).
    Yalnız üretim dili (R178) ve karar anına göre sabit pencere (`ITEM_LOOKBACK`)."""
    window = tuple(
        item
        for item in items
        if item.lang in languages and item.available_at >= decision.decided_at - ITEM_LOOKBACK
    )
    ids = {item.item_id for item in window}
    gates = gates_as_of([row for row in item_rows if row.item_id in ids], decision.decided_at)
    usable = select_items(
        window,
        gates,
        match_id=decision.match_id,
        decided_at=decision.decided_at,
        live=True,
        min_belongs=config.min_belongs,
        min_reliability=config.min_reliability,
    )
    found: tuple[SideTask, ...] = ()
    for side, team in ((HOME, decision.home), (AWAY, decision.away)):
        members = tuple(
            item
            for item in usable
            if item.item_id is not None and gates[item.item_id].side in _MEMBERS[side]
        )
        found = (*found, SideTask(decision, side, team, members, item_set_hash(members)))
    return found


# ── Batarya ────────────────────────────────────────────────────────────────────────────────


def side_battery(questions: QuestionSet, *, side: str, team: str) -> tuple[Question, ...]:
    return tuple(
        for_team(question, side=side, team=team)
        for question in (*questions.tier2, *questions.tier3, *questions.tier4)
    )


def side_state(task: SideTask) -> Mapping[str, Any]:
    decision = task.decision
    return {
        "match": {
            "home": decision.home,
            "away": decision.away,
            "kickoff": decision.kickoff.isoformat(),
        },
        "team": task.team,
        "news": [
            {
                "title": item.title,
                "source": item.source_id,
                "language": item.lang,
                "available_at": item.available_at.isoformat(),
            }
            for item in task.items
        ],
    }


def _valid(answer: ChoiceAnswer, question: Question) -> bool:
    values = (answer.confidence, *answer.probabilities.values())
    return (
        answer.choice in question.criteria
        and set(answer.probabilities) <= set(question.criteria)
        and all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values)
    )


def side_rows(
    task: SideTask,
    battery: Sequence[Question],
    answer: BatteryAnswer,
    *,
    prompt_version: str,
    asked_at: datetime,
) -> tuple[MatchAnswerRow, ...]:
    cost = answer.cost_usd / len(battery)
    return tuple(
        MatchAnswerRow(
            match_id=task.decision.match_id,
            decided_at=task.decision.decided_at,
            prompt_version=prompt_version,
            question_id=question.question_id,
            variant=VARIANT_REAL,
            item_set_hash=task.item_set_hash,
            choice=given.choice,
            probabilities=MappingProxyType(dict(given.probabilities)),
            confidence=given.confidence,
            jev_model=answer.jev_model,
            asked_at=asked_at,
            cost_usd=cost,
        )
        for question in battery
        if (given := answer.answers.get(question.question_id)) is not None
        and _valid(given, question)
    )


# ── Koşucu ─────────────────────────────────────────────────────────────────────────────────

Sink = Callable[[tuple[MatchAnswerRow, ...]], None]


def _discard(rows: tuple[MatchAnswerRow, ...]) -> None:
    return None


def status_row(
    task: SideTask, outcome: str, *, prompt_version: str, at: datetime, jev_model: str = NO_MODEL
) -> MatchAnswerRow:
    return MatchAnswerRow(
        match_id=task.decision.match_id,
        decided_at=task.decision.decided_at,
        prompt_version=prompt_version,
        question_id=status_question(task.side, outcome),
        variant=VARIANT_REAL,
        item_set_hash=task.item_set_hash,
        choice=outcome,
        probabilities=MappingProxyType({outcome: 1.0}),
        confidence=1.0,
        jev_model=jev_model,
        asked_at=at,
        cost_usd=0.0,
    )


def _skip(
    task: SideTask,
    *,
    answered: frozenset[tuple[str, datetime, str]],
    now: datetime,
    config: LiveConfig,
    asked: int,
) -> str | None:
    if task.key in answered:
        return ANSWERED_BEFORE
    if not task.items:
        return NO_NEWS
    if now - task.decision.decided_at > config.max_decision_age:
        return STALE
    if asked >= config.max_sides_per_run:
        return DEFERRED
    return None


def _ask(
    task: SideTask,
    client: JevClient,
    questions: QuestionSet,
    *,
    config: LiveConfig,
    clock: Callable[[], datetime],
) -> tuple[str, tuple[MatchAnswerRow, ...], int, str]:
    """(sonuç, cevap satırları, başarısız soru, dönen model). Tavan çağrıdan ÖNCE düşer."""
    battery = side_battery(questions, side=task.side, team=task.team)
    try:
        answer = client.ask_battery(side_state(task), battery)
    except BudgetExceeded:
        return BUDGET, (), 0, NO_MODEL
    except Exception:
        LOGGER.exception("jev: %s %s sorulamadı", task.decision.match_id, task.side)
        return ERROR, (), len(battery), NO_MODEL
    if config.jev_model is not None and answer.jev_model != config.jev_model:
        return MODEL_DRIFT, (), 0, answer.jev_model
    new = side_rows(task, battery, answer, prompt_version=config.prompt_version, asked_at=clock())
    return ASKED, new, len(battery) - len(new), answer.jev_model


def run_tier2(
    tasks: Sequence[SideTask],
    client: JevClient,
    questions: QuestionSet,
    *,
    config: LiveConfig,
    clock: Callable[[], datetime],
    answered: frozenset[tuple[str, datetime, str]] = frozenset(),
    sink: Sink = _discard,
) -> Tier2Run:
    """Görevleri (karar anı, maç, ev → deplasman) sırasıyla sorar; her tarafın cevapları ve durum
    işareti birlikte `sink`e (I-8). Durunca kalan taraflar durma sebebiyle işaretlenir."""
    outcomes: dict[str, int] = {}
    rows: tuple[MatchAnswerRow, ...] = ()
    failed = streak = 0
    stop: str | None = None
    drift: str | None = None
    for task in sorted(tasks, key=_task_order):
        asked = outcomes.get(ASKED, 0)
        outcome = _skip(task, answered=answered, now=clock(), config=config, asked=asked) or stop
        new: tuple[MatchAnswerRow, ...] = ()
        model = NO_MODEL
        if outcome is None:
            outcome, new, lost, model = _ask(task, client, questions, config=config, clock=clock)
            failed, streak = failed + lost, streak + 1 if outcome == ERROR else 0
            drift = model if outcome == MODEL_DRIFT else drift
            if outcome in (BUDGET, MODEL_DRIFT) or streak >= OUTAGE_STREAK:
                stop = OUTAGE if outcome == ERROR else outcome
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if outcome == ANSWERED_BEFORE:
            continue
        marker = status_row(
            task, outcome, prompt_version=config.prompt_version, at=clock(), jev_model=model
        )
        sink((*new, marker))
        rows = (*rows, *new, marker)
    return Tier2Run(rows, MappingProxyType(outcomes), failed, stop=stop, model_drift=drift)


def _task_order(task: SideTask) -> tuple[datetime, str, int]:
    return task.decision.decided_at, task.decision.match_id, _SIDE_ORDER.index(task.side)


# ── Veritabanı ─────────────────────────────────────────────────────────────────────────────

# Yalnız VARLIK: hiçbir olasılık, fiyat ya da sonuç sütunu okunmaz (I-2; testle sabit).
DECISIONS_SQL = """
    SELECT DISTINCT p.match_id, p.decided_at, m.home_team, m.away_team, m.commence_time
    FROM model_predictions p JOIN matches m ON m.id = p.match_id
    WHERE p.decided_at >= %s AND p.decided_at <= %s AND p.strategy = ANY(%s)
    ORDER BY p.decided_at, p.match_id
"""
# İşaret satırını DIŞLAR (`tests/test_jev_item_answers_readers.py` READERS); sonra `gates_as_of`.
_ITEM_ANSWERS = """
    SELECT item_id, prompt_version, question_id, choice, probabilities, confidence, match_id,
           jev_model, asked_at, cost_usd
    FROM jev_item_answers
    WHERE prompt_version = %s AND item_id = ANY(%s) AND NOT starts_with(question_id, %s)
    ORDER BY item_id, question_id
"""
# Cevaplanmış taraf = `asked` işareti (M-3): başka bir işaret (budget, error…) tarafı kapatmaz.
_ANSWERED = """
    SELECT DISTINCT match_id, decided_at, split_part(question_id, ':', 2)
    FROM jev_match_answers
    WHERE prompt_version = %s AND variant = %s AND match_id = ANY(%s) AND question_id = ANY(%s)
"""
_MATCH_COLUMNS: tuple[tuple[str, str], ...] = (
    ("match_id", "text"),
    ("decided_at", "timestamptz"),
    ("prompt_version", "text"),
    ("question_id", "text"),
    ("variant", "text"),
    ("item_set_hash", "text"),
    ("choice", "text"),
    ("probabilities", "jsonb"),
    ("confidence", "float8"),
    ("jev_model", "text"),
    ("asked_at", "timestamptz"),
    ("cost_usd", "numeric"),
)
_MATCH_NAMES = ", ".join(name for name, _ in _MATCH_COLUMNS)
_MATCH_ARRAYS = ", ".join(f"%({name})s::{kind}[]" for name, kind in _MATCH_COLUMNS)
INSERT_MATCH_ANSWERS = f"""
    INSERT INTO jev_match_answers ({_MATCH_NAMES})
    SELECT {_MATCH_NAMES}
    FROM unnest({_MATCH_ARRAYS}) AS t({_MATCH_NAMES})
    ON CONFLICT (match_id, decided_at, prompt_version, question_id, variant) DO NOTHING
    RETURNING match_id
"""


def load_decisions(
    conn: psycopg.Connection[Any], *, now: datetime, max_age: timedelta
) -> tuple[Decision, ...]:
    with conn.cursor() as cur:
        cur.execute(DECISIONS_SQL, (now - max_age, now, list(SHADOW_STRATEGIES)))
        rows = cur.fetchall()
    return tuple(Decision(str(r[0]), r[1], str(r[2]), str(r[3]), r[4]) for r in rows)


def load_item_answers(
    conn: psycopg.Connection[Any], prompt_version: str, item_ids: Sequence[int]
) -> tuple[ItemAnswerRow, ...]:
    if not item_ids:
        return ()
    with conn.cursor() as cur:
        cur.execute(_ITEM_ANSWERS, (prompt_version, list(item_ids), FAILED_PREFIX))
        rows = cur.fetchall()
    return tuple(
        ItemAnswerRow(
            item_id=int(r[0]),
            prompt_version=str(r[1]),
            question_id=str(r[2]),
            choice=str(r[3]),
            probabilities=MappingProxyType({str(k): float(v) for k, v in dict(r[4]).items()}),
            confidence=float(r[5]),
            match_id=None if r[6] is None else str(r[6]),
            jev_model=str(r[7]),
            asked_at=r[8],
            cost_usd=float(r[9]),
        )
        for r in rows
    )


def answered_sides(
    conn: psycopg.Connection[Any], prompt_version: str, match_ids: Sequence[str]
) -> frozenset[tuple[str, datetime, str]]:
    if not match_ids:
        return frozenset()
    with conn.cursor() as cur:
        cur.execute(_ANSWERED, (prompt_version, VARIANT_REAL, list(match_ids), list(ASKED_MARKERS)))
        return frozenset((str(r[0]), r[1], str(r[2])) for r in cur.fetchall())


def _column(row: MatchAnswerRow, name: str) -> Any:
    value = getattr(row, name)
    return json.dumps(dict(value), sort_keys=True) if name == "probabilities" else value


def write_match_answers(conn: psycopg.Connection[Any], rows: Sequence[MatchAnswerRow]) -> int:
    """YENİ yazılan satır sayısı; aynı (maç, karar, küme, soru, varyant) ikinci kez yazılmaz."""
    if not rows:
        return 0
    columns = {name: [_column(row, name) for row in rows] for name, _ in _MATCH_COLUMNS}
    with conn.cursor() as cur:
        cur.execute(INSERT_MATCH_ANSWERS, columns)
        return len(cur.fetchall())


def collect_tasks(
    conn: psycopg.Connection[Any],
    *,
    config: LiveConfig,
    languages: frozenset[str],
    now: datetime,
) -> tuple[tuple[Decision, ...], tuple[SideTask, ...]]:
    decisions = load_decisions(conn, now=now, max_age=config.max_decision_age)
    if not decisions:
        return (), ()
    items = load_news(conn, since=min(d.decided_at for d in decisions) - ITEM_LOOKBACK)
    ids = [item.item_id for item in items if item.item_id is not None]
    rows = load_item_answers(conn, config.tier1_prompt_version, ids)
    tasks = tuple(
        task
        for decision in decisions
        for task in side_tasks(decision, items, rows, config=config, languages=languages)
    )
    return decisions, tasks
