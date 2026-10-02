"""TFF baş hakem atamasını `matches` satırına bağlar ve değişikliği kaydeder (spec 2026-10-02 §4).

Takım adı eşlemesi `config/tff_teams.yaml`dır: anahtar `normalise_team(TFF adı)`, değer bu sezon
`matches`te (`league_id = tur.1`) GÖRÜLEN The Odds API yazımı ya da `null` (yazım henüz görülmedi —
uydurulmaz; o takımın maçı `awaiting_alias` sayılır, hata değil). YAML'da HİÇ olmayan ad
`ContractViolation`dır (yapılandırma eksiği; düzeltme YAML'a satır).

Bağlama gözlem tablosunu OKUMAZ: `collect_tff`in o turda ayrıştırdığı gözlemlerden çalışır; bu
yüzden `latest_observations`in X→Y→X sınırlaması (DEFERRED 9.6e, I-5) burada oluşmaz. Maç, TFF
tarihinin Europe/Istanbul takvim günüyle bulunur; saat uyuşmazlığı eşlemeyi bozmaz.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
import yaml

from football_edge.collector import ContractViolation, Observation
from football_edge.naming import normalise_team

LOGGER = logging.getLogger("football_edge.officials")

TFF_TEAMS_PATH = Path("config/tff_teams.yaml")
ISTANBUL = ZoneInfo("Europe/Istanbul")
# 0015'in `check (length(referee) between 1 and 80)`ü ve şemanın `$defs.person`ı. `verify-snapshot`
# H2c işaretleri burada da reddedilir: bozuk bir ad ilk kez dışa aktarımda görülürse BÜTÜN site
# durur.
REFEREE_MAX = 80
_UNSAFE = ("http", "<", ">")
_TOP_KEYS = frozenset({"league_label_contains", "league_id", "teams"})
# Controller düzeltmesi C1: bu sözcüklerden birini taşıyan etiket kadın/genç ligidir, işlenmez.
_EXCLUDED_LEAGUE_WORDS = ("kadın", "kadin", "u19", "u21", "gelişim", "gelisim")

_CANDIDATES = (
    "SELECT id, home_team, away_team, commence_time FROM matches "
    "WHERE league_id = %s AND commence_time >= %s AND commence_time < %s"
)
_LATEST = (
    "SELECT DISTINCT ON (match_id) match_id, referee FROM match_officials "
    "WHERE match_id = ANY(%s) ORDER BY match_id, seen_at DESC, id DESC"
)
_INSERT = "INSERT INTO match_officials (match_id, referee, seen_at) VALUES (%s, %s, %s)"

_Key = tuple[str, str, date]  # (API ev adı, API deplasman adı, İstanbul günü)


@dataclass(frozen=True)
class TeamMap:
    league_label_contains: str  # bu ifadeyi TAM ifade olarak TAŞIYAN TFF lig bloğu işlenir (C1)
    league_id: str  # `matches.league_id` hedefi
    teams: Mapping[str, str | None]  # normalise_team(TFF adı) → API adı | None

    def matches_league(self, label: str) -> bool:
        """Etiket `league_label_contains`ı TAM ifade olarak taşır ("Süper Ligi" eşleşmez) ve
        kadın/genç ligi bloğu değildir (controller düzeltmesi C1). Etiket de aranan ifade de
        `fold_label`dan geçer (son inceleme M2): yalnız biri katlanırsa "SÜPER LİG" yazımı sessizce
        lig dışı kalır."""
        folded = fold_label(label)
        if any(word in folded for word in _EXCLUDED_LEAGUE_WORDS):
            return False
        phrase = re.escape(fold_label(self.league_label_contains)) + r"(?!\w)"
        return re.search(phrase, folded) is not None


def fold_label(text: str) -> str:
    """`İ` önce `i`ye katlanır: yalnız `casefold` onu `i̇` yapar ve "LİG" "lig" ile eşleşmez."""
    return text.replace("İ", "i").casefold()


@dataclass(frozen=True)
class Assignment:
    league: str  # TFF lig bloğunun etiketi
    home: str  # TFF yazımı
    away: str
    referee: str
    match_date: date  # TFF'nin (İstanbul) tarihi


@dataclass(frozen=True)
class Candidate:
    match_id: str
    home: str  # API yazımı
    away: str
    commence_time: datetime


@dataclass(frozen=True)
class LinkPlan:
    links: tuple[tuple[str, str], ...]  # (match_id, referee), match_id sırasıyla
    not_in_db: int
    awaiting_alias: int
    other_league: int


@dataclass(frozen=True)
class LinkResult:
    linked: int
    written: int
    not_in_db: int
    awaiting_alias: int
    other_league: int


def load_team_map(path: Path = TFF_TEAMS_PATH) -> TeamMap:
    """Biçim dışı her dosya `ValueError`dır; mesaj yolu ve kuralı adlandırır."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != _TOP_KEYS:
        raise ValueError(f"{path}: üst anahtarlar {sorted(_TOP_KEYS)} olmalı")
    label, league_id, teams = raw["league_label_contains"], raw["league_id"], raw["teams"]
    if not (isinstance(label, str) and label and isinstance(league_id, str) and league_id):
        raise ValueError(f"{path}: league_label_contains ve league_id boş olmayan metin olmalı")
    if not isinstance(teams, dict) or not teams:
        raise ValueError(f"{path}: teams boş olmayan bir eşleme olmalı")
    return TeamMap(label, league_id, _checked_teams(path, teams))


def _checked_teams(path: Path, teams: Mapping[Any, Any]) -> dict[str, str | None]:
    for key, value in teams.items():
        if not isinstance(key, str) or normalise_team(key) != key:
            raise ValueError(f"{path}: anahtar normalise_team çıktısı değil: {key!r}")
        if value is not None and not (isinstance(value, str) and value.strip()):
            raise ValueError(f"{path}: {key!r} değeri null ya da boş olmayan metin olmalı")
        if isinstance(value, str) and value != value.strip():
            # API yazımı `matches`le birebir karşılaştırılır; görünmez boşluk her maçı `not_in_db`
            # yapar ve kimse fark etmez (son inceleme M2).
            raise ValueError(f"{path}: {key!r} değeri baş/son boşluk taşımamalı: {value!r}")
    return {str(key): value for key, value in teams.items()}


def istanbul_day(moment: datetime) -> date:
    """`commence_time`ın Europe/Istanbul takvim günü; saat dilimsiz an reddedilir."""
    if moment.utcoffset() is None:
        raise ValueError("istanbul_day saat dilimi taşımayan datetime kabul etmez")
    return moment.astimezone(ISTANBUL).date()


def assignment_of(entry: Observation) -> Assignment:
    payload = entry.payload
    return Assignment(
        str(payload["league"]),
        str(payload["home_team"]),
        str(payload["away_team"]),
        str(payload["referee"]),
        date.fromisoformat(str(payload["match_date"])),
    )


def plan_links(
    assignments: Sequence[Assignment],
    candidates: Sequence[Candidate],
    team_map: TeamMap,
) -> LinkPlan:
    """Saf eşleme (spec §4): DB yok, saat yok. Kırmızı `ContractViolation`dır; sayaçlar loglanır."""
    index = _index(candidates)
    links: dict[str, str] = {}
    not_in_db = awaiting = other = 0
    for item in assignments:
        if not team_map.matches_league(item.league):
            other += 1
            continue
        _check_referee(item)
        home, away = _api_name(item.home, item, team_map), _api_name(item.away, item, team_map)
        if home is None or away is None:
            awaiting += 1
            _warn_unlinked("alias bekleyen", item)
            continue
        found = index.get((home, away, item.match_date), ())
        if len(found) > 1:
            raise ContractViolation(
                f"tff: {item.home} – {item.away} ({item.match_date}) için {len(found)} maç "
                f"({', '.join(sorted(found))}) — aynı İstanbul gününde birden çok eşleşme"
            )
        if not found:
            not_in_db += 1
            _warn_unlinked("DB'de yok", item)
            _warn_if_reversed(index, (home, away), item)
            continue
        links = _with_link(links, found[0], item.referee)
    if other == len(assignments):
        _warn_if_label_drifted(assignments, team_map)
    return LinkPlan(tuple(sorted(links.items())), not_in_db, awaiting, other)


def _warn_unlinked(counter: str, item: Assignment) -> None:
    """Son inceleme I1: sayaç tek başına hangi maçın düştüğünü söylemez; satır adıyla loglanır."""
    LOGGER.warning(
        "tff: %s – %s (%s) bağlanmadı: %s",
        item.home,
        item.away,
        item.match_date.isoformat(),
        counter,
    )


def _warn_if_label_drifted(assignments: Sequence[Assignment], team_map: TeamMap) -> None:
    """Hiçbir blok lig ifadesiyle eşleşmezken ifadeyi alt dize olarak taşıyan etiket (dışlananlar
    dahil) TFF'nin etiketi değiştirdiğine işaret olabilir; aksi hâlde hafta `other_league`a düşer
    ve sessizce boş geçer (son inceleme I1)."""
    phrase = fold_label(team_map.league_label_contains)
    for label in sorted({item.league for item in assignments if phrase in fold_label(item.league)}):
        LOGGER.warning("tff: lig etiketi değişmiş olabilir: %s", label)


def _check_referee(item: Assignment) -> None:
    text = item.referee
    if not 1 <= len(text) <= REFEREE_MAX or any(mark in text.lower() for mark in _UNSAFE):
        raise ContractViolation(
            f"tff: {item.home} – {item.away} hakem metni sözleşme dışı "
            f"(1–{REFEREE_MAX} karakter, bağlantı/işaretleme yok)"
        )


def _api_name(tff_name: str, item: Assignment, team_map: TeamMap) -> str | None:
    key = normalise_team(tff_name)
    if key not in team_map.teams:
        raise ContractViolation(
            f"tff: {tff_name!r} ({item.league}) {TFF_TEAMS_PATH} teams'te yok — yapılandırma "
            f"eksiği; düzeltme: YAML'a satır (anahtar {key!r})"
        )
    return team_map.teams[key]


def _index(candidates: Sequence[Candidate]) -> dict[_Key, tuple[str, ...]]:
    index: dict[_Key, tuple[str, ...]] = {}
    for candidate in candidates:
        key = (candidate.home, candidate.away, istanbul_day(candidate.commence_time))
        index[key] = (*index.get(key, ()), candidate.match_id)
    return index


def _warn_if_reversed(
    index: Mapping[_Key, tuple[str, ...]], names: tuple[str, str], item: Assignment
) -> None:
    """Ters sırayla var olan maç tahminle bağlanmaz, ama haftalarca sessizce kaybolmasın."""
    home, away = names
    if index.get((away, home, item.match_date)):
        LOGGER.warning(
            "tff: %s – %s (%s) DB'de ters ev/deplasman sırasıyla var — bağlanmadı",
            item.home,
            item.away,
            item.match_date.isoformat(),
        )


def _with_link(links: Mapping[str, str], match_id: str, referee: str) -> dict[str, str]:
    known = links.get(match_id)
    if known is not None and known != referee:
        raise ContractViolation(
            f"tff: aynı maç ({match_id}) bu turda iki farklı hakemle — {known!r} / {referee!r}"
        )
    return {**links, match_id: referee}


def pending_writes(
    links: Sequence[tuple[str, str]], latest: Mapping[str, str], now: datetime
) -> tuple[tuple[str, str, datetime], ...]:
    """Değişiklik kaydı: maçın SON kayıtlı hakemi farklıysa ya da hiç yoksa bir satır."""
    return tuple(
        (match_id, referee, now) for match_id, referee in links if latest.get(match_id) != referee
    )


def find_candidates(
    conn: psycopg.Connection[Any], league_id: str, days: Sequence[date]
) -> tuple[Candidate, ...]:
    """Verilen İstanbul günlerini kapsayan aralıktaki maçlar; sınırlar İstanbul gece yarısıdır."""
    if not days:
        return ()
    start = datetime.combine(min(days), time(0), tzinfo=ISTANBUL)
    end = datetime.combine(max(days) + timedelta(days=1), time(0), tzinfo=ISTANBUL)
    with conn.cursor() as cur:
        cur.execute(_CANDIDATES, (league_id, start, end))
        rows = cur.fetchall()
    return tuple(Candidate(str(row[0]), str(row[1]), str(row[2]), row[3]) for row in rows)


def _latest_referees(conn: psycopg.Connection[Any], match_ids: Sequence[str]) -> dict[str, str]:
    if not match_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(_LATEST, (list(match_ids),))
        return {str(row[0]): str(row[1]) for row in cur.fetchall()}


def link_officials(
    conn: psycopg.Connection[Any],
    observations: Sequence[Observation],
    *,
    team_map: TeamMap,
    now: datetime,
) -> LinkResult:
    """Turun ayrıştırılmış sonucunu bağlar ve değişeni `match_officials`e yazar; commit eder."""
    assignments = tuple(assignment_of(entry) for entry in observations)
    days = sorted({item.match_date for item in assignments if team_map.matches_league(item.league)})
    plan = plan_links(assignments, find_candidates(conn, team_map.league_id, days), team_map)
    latest = _latest_referees(conn, [match_id for match_id, _ in plan.links])
    rows = pending_writes(plan.links, latest, now)
    if rows:
        with conn.cursor() as cur:
            cur.executemany(_INSERT, rows)
    conn.commit()
    return LinkResult(
        len(plan.links), len(rows), plan.not_in_db, plan.awaiting_alias, plan.other_league
    )
