"""Kademe 1: haber başına T1 kapı soruları (spec §6; R164, §5.3 rolleri).

Her haber için TEK batarya çağrısı. Seçenekleri KOD kurar, Jev yalnız seçer (`mapping.py` deseni:
model listede olmayanı seçemez, listede olmayan bir değer dönerse cevap geçersizdir):

- **Maç ve taraf (`t1_mac_taraf`)**: adaylar, başlama anı haberin `available_at`inden SONRA ve en
  çok `HORIZON` (8 gün) içinde olan ve takımlarından en az birinin adı haber metninde geçen
  fikstürlerdir. Ad eşleşmesi aksansız, küçük harfli sözcük önekidir (`Beşiktaş'ta`,
  `Galatasaraylı` → `besiktas`, `galatasaray`); en çok iki takımı geçen önde, sonra erken başlayan,
  en çok `MAX_FIXTURES`. Her aday üç seçenektir (`<match_id>:home|away|both`) ve `NO_MATCH` her
  zaman listededir (`questions.ALWAYS`). Adı geçmeyen fikstür aday olamaz: aday yoksa Jev
  çağrılmaz, haber "adaysız" sayılır (takma adla — "Cimbom" — yazılmış haber burada kaybolur;
  bilinen sınır).
- **Küme (`t1_kume`) ve çelişki (`t1_celiski`)**: aynı takımlardan birini anan, (zaman, kimlik)
  sırasında bu haberden önce gelen ve en çok `CLUSTER_WINDOW` eski haberler; en yeni
  `MAX_EARLIER` tanesi. Önceki haber yoksa bu iki soru sorulmaz ve haber kendi kümesidir.
- **Güvenilirlik (`t1_guvenilirlik`)**: seçenekleri soru dosyasında.

Cevap `asked_at` = çağrı DÖNDÜKTEN sonraki an: canlıda `asked_at < decided_at` bu ana bakar.

Yeniden deneme sınırı (son inceleme I-3): cevapsız kalan her deneme (Jev hatası ya da geçersiz/eksik
maç cevabı) `jev_item_answers`e numaralı bir İŞARET satırı bırakır — `question_id` =
`t1_failed:<n>`, `choice` = sebep, olasılık yok, maliyet 0 (harcama `jev_spend`te). Yeni tablo yok,
satır yalnız eklenir. İşaret "sorulmuş" sayılmaz (`asked_item_ids`), kapıya girmez (`gates_from`);
`MAX_ATTEMPTS` işareti olan haber bu `prompt_version` için bir daha satın alınmaz.

Kesinti (DEFERRED 17b): koşuda en az bir haber sorulduysa ve sorulan HER haber Jev hatasıyla
(`REASON_ERROR`) düştüyse — hiç cevap, hiç geçersiz cevap yok — düşüş haberin değil Jev'in
sonucudur. O koşu işaret bırakmaz ve `Tier1Run.outage` ile bildirilir; yoksa üç kesinti koşusu
haberleri bu `prompt_version` için kalıcı olarak kapsam dışı bırakırdı. Karışık koşu ve tavan
duruşu işaretlerini bugünkü gibi bırakır.
"""

from __future__ import annotations

import json
import logging
import math
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any

import psycopg

from football_edge.features.questions import (
    CLUSTER_QUESTION,
    CONFLICT_QUESTION,
    MATCH_QUESTION,
    RELIABILITY_QUESTION,
    RELIABLE_CHOICES,
    QuestionSet,
)
from football_edge.features.types import AWAY, BOTH, HOME, SIDES, ItemGate, StoredNews
from football_edge.jev import BatteryAnswer, ChoiceAnswer, JevClient, Question
from football_edge.jev_budget import BudgetExceeded
from football_edge.live.context import LiveMatch
from football_edge.naming import normalise_team

LOGGER = logging.getLogger("football_edge.features.tier1")

HORIZON = timedelta(days=8)
CLUSTER_WINDOW = timedelta(hours=72)
MAX_FIXTURES = 6
MAX_EARLIER = 8
MIN_TOKEN = 4
EARLIER_PREFIX = "item:"
FAILED_PREFIX = "t1_failed:"
MAX_ATTEMPTS = 3
REASON_INVALID = "match_invalid"
REASON_ERROR = "jev_error"
# Hata çağrısında model bilinmez; 0012 `jev_model`i NOT NULL ister.
NO_MODEL = "-"
# Birçok kulüp adında geçen, tek başına kulüp ayırt etmeyen sözcükler.
GENERIC_TOKENS = frozenset(
    {
        "athletic",
        "atletico",
        "borussia",
        "city",
        "club",
        "county",
        "deportivo",
        "istanbul",
        "olympique",
        "racing",
        "real",
        "royal",
        "saint",
        "sporting",
        "town",
        "united",
    }
)


@dataclass(frozen=True)
class ItemAnswerRow:
    item_id: int
    prompt_version: str
    question_id: str
    choice: str
    probabilities: Mapping[str, float]
    confidence: float
    match_id: str | None
    jev_model: str
    asked_at: datetime
    cost_usd: float


@dataclass(frozen=True)
class Tier1Run:
    rows: tuple[ItemAnswerRow, ...]
    asked: int  # sorulan soru
    failed: int  # cevapsız ya da geçersiz cevaplı soru
    no_candidate: int  # adayı olmadığı için sorulmayan haber
    budget_hit: bool  # tavan: kalan haberler sorulmadı
    failures: tuple[ItemAnswerRow, ...] = ()  # cevapsız denemelerin işaretleri (`FAILED_PREFIX`)
    given_up: int = 0  # `MAX_ATTEMPTS` kez başarısız olduğu için sorulmayan haber
    outage: bool = False  # sorulan her haber Jev hatasıyla düştü: işaret dönülmez (17b)


# ── Adaylar ────────────────────────────────────────────────────────────────────────────────


def fold(text: str) -> str:
    """Aksansız eşleşme anahtarı: `normalise_team` + birleştirici işaretlerin atılması."""
    decomposed = unicodedata.normalize("NFKD", text)
    bare = "".join(char for char in decomposed if not unicodedata.combining(char))
    return normalise_team(bare)


def team_tokens(name: str) -> frozenset[str]:
    words = fold(name).split()
    significant = frozenset(w for w in words if len(w) >= MIN_TOKEN and w not in GENERIC_TOKENS)
    return significant or frozenset(words)


def _words(item: StoredNews) -> frozenset[str]:
    return frozenset(fold(f"{item.title} {item.body or ''}").split())


def _mentions(team: str, words: frozenset[str]) -> bool:
    tokens = team_tokens(team)
    return any(word.startswith(token) for token in tokens for word in words)


def candidate_fixtures(item: StoredNews, fixtures: Sequence[LiveMatch]) -> tuple[LiveMatch, ...]:
    words = _words(item)
    scored = [
        (hits, fixture)
        for fixture in fixtures
        if item.available_at < fixture.kickoff <= item.available_at + HORIZON
        and (hits := sum(_mentions(team, words) for team in (fixture.home, fixture.away)))
    ]
    scored.sort(key=lambda entry: (-entry[0], entry[1].kickoff, entry[1].match_id))
    return tuple(fixture for _, fixture in scored[:MAX_FIXTURES])


def _order(item: StoredNews) -> tuple[datetime, int]:
    if item.item_id is None:
        raise ValueError(f"{item.url}: yazılmamış haber kademe 1'e giremez")
    return item.available_at, item.item_id


def cluster_candidates(
    item: StoredNews, pool: Sequence[StoredNews], fixtures: Sequence[LiveMatch]
) -> tuple[StoredNews, ...]:
    teams = {team for fixture in fixtures for team in (fixture.home, fixture.away)}
    earlier = sorted(
        (
            other
            for other in pool
            if _order(other) < _order(item)
            and other.available_at >= item.available_at - CLUSTER_WINDOW
            and any(_mentions(team, _words(other)) for team in teams)
        ),
        key=_order,
    )
    return tuple(earlier[-MAX_EARLIER:])


# ── Batarya ────────────────────────────────────────────────────────────────────────────────


def _kickoff(fixture: LiveMatch) -> str:
    return fixture.kickoff.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def match_question(template: Question, fixtures: Sequence[LiveMatch]) -> Question:
    criteria: dict[str, str] = {}
    for fixture in fixtures:
        label = f"{fixture.home} v {fixture.away}, {_kickoff(fixture)}"
        criteria[f"{fixture.match_id}:{HOME}"] = f"{label}: mainly about {fixture.home}"
        criteria[f"{fixture.match_id}:{AWAY}"] = f"{label}: mainly about {fixture.away}"
        criteria[f"{fixture.match_id}:{BOTH}"] = f"{label}: about both teams or the match itself"
    return Question(template.question_id, template.instructions, {**criteria, **template.criteria})


def cluster_question(template: Question, earlier: Sequence[StoredNews]) -> Question:
    criteria = {
        f"{EARLIER_PREFIX}{other.item_id}": f"Same event as: {other.title}" for other in earlier
    }
    return Question(template.question_id, template.instructions, {**criteria, **template.criteria})


def _battery(
    templates: Mapping[str, Question],
    fixtures: Sequence[LiveMatch],
    earlier: Sequence[StoredNews],
) -> tuple[Question, ...]:
    about_earlier = (
        (cluster_question(templates[CLUSTER_QUESTION], earlier), templates[CONFLICT_QUESTION])
        if earlier
        else ()
    )
    return (
        match_question(templates[MATCH_QUESTION], fixtures),
        *about_earlier,
        templates[RELIABILITY_QUESTION],
    )


def _state(
    item: StoredNews, fixtures: Sequence[LiveMatch], earlier: Sequence[StoredNews]
) -> Mapping[str, Any]:
    return {
        "news": {
            "title": item.title,
            "body": item.body or "",
            "language": item.lang,
            "source": item.source_id,
            "available_at": item.available_at.isoformat(),
        },
        "fixtures": [{"home": f.home, "away": f.away, "kickoff": _kickoff(f)} for f in fixtures],
        "earlier_news": [
            {"id": f"{EARLIER_PREFIX}{other.item_id}", "title": other.title} for other in earlier
        ],
    }


def _valid(answer: ChoiceAnswer, question: Question) -> bool:
    """Tip cevabın şeklini garanti eder, doğruluğunu değil: listede olmayan seçim geçersizdir."""
    values = (answer.confidence, *answer.probabilities.values())
    return (
        answer.choice in question.criteria
        and set(answer.probabilities) <= set(question.criteria)
        and all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values)
    )


def _answer_rows(
    item_id: int,
    battery: Sequence[Question],
    answer: BatteryAnswer,
    *,
    prompt_version: str,
    asked_at: datetime,
) -> tuple[ItemAnswerRow, ...]:
    valid = {
        question.question_id: given
        for question in battery
        if (given := answer.answers.get(question.question_id)) is not None
        and _valid(given, question)
    }
    match = valid.get(MATCH_QUESTION)
    if match is None:
        # Maç cevabı yoksa haber kapısızdır; öbür satırlar yazılsaydı `asked_item_ids` onu
        # "sorulmuş" sayar, bu `prompt_version` için bir daha sormazdı. Hiç satır: yeniden sorulur.
        return ()
    match_id = _split(match.choice)[0]
    # Maliyet sorulan soru başınadır: cevapsız sorunun payı satırsız kalır, toplam `jev_spend`te.
    cost = answer.cost_usd / len(battery)
    return tuple(
        ItemAnswerRow(
            item_id=item_id,
            prompt_version=prompt_version,
            question_id=question_id,
            choice=given.choice,
            probabilities=MappingProxyType(dict(given.probabilities)),
            confidence=given.confidence,
            match_id=match_id,
            jev_model=answer.jev_model,
            asked_at=asked_at,
            cost_usd=cost,
        )
        for question_id, given in valid.items()
    )


def is_failure(row: ItemAnswerRow) -> bool:
    return row.question_id.startswith(FAILED_PREFIX)


def _failure(
    item_id: int,
    attempt: int,
    outcome: BatteryAnswer | str,
    *,
    prompt_version: str,
    at: datetime,
) -> ItemAnswerRow:
    """Cevapsız denemenin işareti: `outcome` Jev hatasının sebebi ya da geçersiz cevaplı yanıt."""
    return ItemAnswerRow(
        item_id=item_id,
        prompt_version=prompt_version,
        question_id=f"{FAILED_PREFIX}{attempt}",
        choice=outcome if isinstance(outcome, str) else REASON_INVALID,
        probabilities=MappingProxyType({}),
        confidence=0.0,
        match_id=None,
        jev_model=NO_MODEL if isinstance(outcome, str) else outcome.jev_model,
        asked_at=at,
        cost_usd=0.0,
    )


def _ask(
    client: JevClient, state: Mapping[str, Any], battery: Sequence[Question], item_id: int
) -> BatteryAnswer | str:
    """Yanıt ya da başarısızlık sebebi. Tavan (`BudgetExceeded`) çağırana çıkar: koşu durur."""
    try:
        return client.ask_battery(state, battery)
    except BudgetExceeded:
        raise
    except Exception as error:
        LOGGER.exception("jev: haber %s sorulamadı", item_id)
        return f"{REASON_ERROR}:{type(error).__name__}"


def _is_outage(rows: Sequence[ItemAnswerRow], failures: Sequence[ItemAnswerRow]) -> bool:
    """Sorulan her haber işaret aldı (cevap yok) ve her işaret bir Jev hatasıdır."""
    return (
        bool(failures)
        and not rows
        and all(marker.choice.startswith(f"{REASON_ERROR}:") for marker in failures)
    )


def _split(choice: str) -> tuple[str | None, str | None]:
    """`<match_id>:<taraf>` → (maç, taraf); başka her seçim (NO_MATCH) → (None, None)."""
    match_id, _, side = choice.rpartition(":")
    return (match_id, side) if match_id and side in SIDES else (None, None)


def run_tier1(
    items: Sequence[StoredNews],
    client: JevClient,
    questions: QuestionSet,
    *,
    fixtures: Sequence[LiveMatch],
    clock: Callable[[], datetime],
    history: Sequence[StoredNews] = (),
    attempts: Mapping[int, int] = MappingProxyType({}),
) -> Tier1Run:
    """`items`i (zaman, kimlik) sırasıyla sorar; `history` yalnız küme adayıdır, sorulmaz.

    Tavan (`BudgetExceeded`) çağrıdan ÖNCE düşer: o ana kadarki cevaplar kaybolmaz, dönülür.
    Başka bir Jev hatası yalnız o haberi düşürür; soruları başarısız sayılır. `attempts` haber
    başına önceki başarısız deneme sayısıdır: `MAX_ATTEMPTS`e ulaşan haber sorulmaz. Sorulan her
    haber Jev hatasıyla düştüyse koşu kesintidir: `outage`, işaretsiz (modül belgesi).
    """
    templates = {question.question_id: question for question in questions.tier1}
    pool = (*history, *items)
    rows: tuple[ItemAnswerRow, ...] = ()
    failures: tuple[ItemAnswerRow, ...] = ()
    asked = failed = no_candidate = given_up = 0
    for item in sorted(items, key=_order):
        item_id = _order(item)[1]
        attempt = attempts.get(item_id, 0) + 1
        if attempt > MAX_ATTEMPTS:
            given_up += 1
            continue
        candidates = candidate_fixtures(item, fixtures)
        if not candidates:
            no_candidate += 1
            continue
        earlier = cluster_candidates(item, pool, candidates)
        battery = _battery(templates, candidates, earlier)
        try:
            answer = _ask(client, _state(item, candidates, earlier), battery, item_id)
        except BudgetExceeded:
            return Tier1Run(
                rows,
                asked,
                failed,
                no_candidate,
                budget_hit=True,
                failures=failures,
                given_up=given_up,
            )
        at = clock()
        new = (
            ()
            if isinstance(answer, str)
            else _answer_rows(
                item_id, battery, answer, prompt_version=questions.prompt_version, asked_at=at
            )
        )
        asked, failed = asked + len(battery), failed + len(battery) - len(new)
        rows = (*rows, *new)
        if not new:
            marker = _failure(
                item_id, attempt, answer, prompt_version=questions.prompt_version, at=at
            )
            failures = (*failures, marker)
    outage = _is_outage(rows, failures)
    return Tier1Run(
        rows,
        asked,
        failed,
        no_candidate,
        budget_hit=False,
        failures=() if outage else failures,
        given_up=given_up,
        outage=outage,
    )


# ── Kapı özeti ─────────────────────────────────────────────────────────────────────────────


def _belongs(row: ItemAnswerRow) -> float:
    if row.match_id is None:
        return 0.0
    # Haberin maça ait olma olasılığı tarafın üç seçeneğinin toplamıdır (taraf ayrı bir yargı).
    return math.fsum(p for key, p in row.probabilities.items() if _split(key)[0] == row.match_id)


def _reliability(row: ItemAnswerRow | None) -> float:
    # Cevapsız güvenilirlik 0'dır: bilinmeyen güvenilirlik eşiği geçmez.
    if row is None:
        return 0.0
    return math.fsum(row.probabilities.get(key, 0.0) for key in RELIABLE_CHOICES)


def _parent(row: ItemAnswerRow | None) -> int | None:
    if row is None or not row.choice.startswith(EARLIER_PREFIX):
        return None
    text = row.choice.removeprefix(EARLIER_PREFIX)
    return int(text) if text.isdigit() else None


def _root(item_id: int, parents: Mapping[int, int | None]) -> int:
    seen = {item_id}
    current = item_id
    while (parent := parents.get(current)) is not None and parent not in seen:
        seen.add(parent)
        current = parent
    return current


def gates_from(rows: Sequence[ItemAnswerRow]) -> Mapping[int, ItemGate]:
    """Haber başına kapı özeti; maç sorusu cevapsız haberin kapısı yoktur (hiçbir maça giremez)."""
    if len({row.prompt_version for row in rows}) > 1:
        raise ValueError("gates_from tek bir prompt_version'ın cevaplarını ister")
    by_item: dict[int, dict[str, ItemAnswerRow]] = {}
    # Başarısızlık işareti cevap değildir: `asked_at`i ve kapıyı etkilemez.
    for row in (row for row in rows if not is_failure(row)):
        by_item.setdefault(row.item_id, {})[row.question_id] = row
    parents = {
        item_id: _parent(answers.get(CLUSTER_QUESTION)) for item_id, answers in by_item.items()
    }
    gates: dict[int, ItemGate] = {}
    for item_id, answers in by_item.items():
        match = answers.get(MATCH_QUESTION)
        if match is None:
            continue
        gates[item_id] = ItemGate(
            item_id=item_id,
            match_id=match.match_id,
            side=_split(match.choice)[1],
            belongs=_belongs(match),
            reliability=_reliability(answers.get(RELIABILITY_QUESTION)),
            cluster_id=str(_root(item_id, parents)),
            asked_at=max(row.asked_at for row in answers.values()),
        )
    return MappingProxyType(gates)


# ── Veritabanı ─────────────────────────────────────────────────────────────────────────────

# `live.store`un aynı sorgusu burada yinelenir: özellik paketi `live.store`u import edemez
# (spec §5/4) — o modül kapanış ve sonuç okuyucularını da taşır.
_FIXTURES = """
    SELECT id, league_id, commence_time, home_team, away_team
    FROM matches
    WHERE commence_time > %s AND commence_time <= %s
    ORDER BY commence_time, id
"""
# İşaret satırı "sorulmuş" saymaz: yalnız başarısız denemesi olan haber yeniden sorulur.
_ASKED = """
    SELECT DISTINCT item_id FROM jev_item_answers
    WHERE prompt_version = %s AND item_id = ANY(%s) AND NOT starts_with(question_id, %s)
"""
_ATTEMPTS = """
    SELECT item_id, count(*) FROM jev_item_answers
    WHERE prompt_version = %s AND item_id = ANY(%s) AND starts_with(question_id, %s)
    GROUP BY item_id
"""
_ANSWER_COLUMNS: tuple[tuple[str, str], ...] = (
    ("item_id", "bigint"),
    ("prompt_version", "text"),
    ("question_id", "text"),
    ("choice", "text"),
    ("probabilities", "jsonb"),
    ("confidence", "float8"),
    ("match_id", "text"),
    ("jev_model", "text"),
    ("asked_at", "timestamptz"),
    ("cost_usd", "numeric"),
)
_ANSWER_NAMES = ", ".join(name for name, _ in _ANSWER_COLUMNS)
_ANSWER_ARRAYS = ", ".join(f"%({name})s::{kind}[]" for name, kind in _ANSWER_COLUMNS)
INSERT_ITEM_ANSWERS = f"""
    INSERT INTO jev_item_answers ({_ANSWER_NAMES})
    SELECT {_ANSWER_NAMES}
    FROM unnest({_ANSWER_ARRAYS}) AS t({_ANSWER_NAMES})
    ON CONFLICT (item_id, prompt_version, question_id) DO NOTHING
    RETURNING item_id
"""


def load_fixtures(
    conn: psycopg.Connection[Any], *, since: datetime, until: datetime
) -> tuple[LiveMatch, ...]:
    with conn.cursor() as cur:
        cur.execute(_FIXTURES, (since, until))
        rows = cur.fetchall()
    return tuple(
        LiveMatch(str(row[0]), str(row[1]), row[2], str(row[3]), str(row[4])) for row in rows
    )


def asked_item_ids(
    conn: psycopg.Connection[Any], prompt_version: str, item_ids: Sequence[int]
) -> frozenset[int]:
    if not item_ids:
        return frozenset()
    with conn.cursor() as cur:
        cur.execute(_ASKED, (prompt_version, list(item_ids), FAILED_PREFIX))
        return frozenset(int(row[0]) for row in cur.fetchall())


def failed_attempts(
    conn: psycopg.Connection[Any], prompt_version: str, item_ids: Sequence[int]
) -> Mapping[int, int]:
    """Haber başına bu `prompt_version`daki başarısız deneme (işaret satırı) sayısı."""
    if not item_ids:
        return MappingProxyType({})
    with conn.cursor() as cur:
        cur.execute(_ATTEMPTS, (prompt_version, list(item_ids), FAILED_PREFIX))
        return MappingProxyType({int(row[0]): int(row[1]) for row in cur.fetchall()})


def _column(row: ItemAnswerRow, name: str) -> Any:
    value = getattr(row, name)
    return json.dumps(dict(value), sort_keys=True) if name == "probabilities" else value


def write_item_answers(conn: psycopg.Connection[Any], rows: Sequence[ItemAnswerRow]) -> int:
    """YENİ yazılan cevap sayısı; aynı (haber, sürüm, soru) ikinci kez yazılmaz."""
    if not rows:
        return 0
    columns = {name: [_column(row, name) for row in rows] for name, _ in _ANSWER_COLUMNS}
    with conn.cursor() as cur:
        cur.execute(INSERT_ITEM_ANSWERS, columns)
        return len(cur.fetchall())
