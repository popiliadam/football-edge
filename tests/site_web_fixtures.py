"""B-2'nin sentetik anlık görüntü fixture'ları: TEK kaynak burası, JSON dosyaları bunun çıktısı.

Uydurma lig/takım adları, gerçek satır yok (spec §5.2). Dosyalar elle düzenlenmez:
`uv run python -m tests.site_web_fixtures` yeniden yazar; `test_site_web_contract.py`
depodaki dosyaların bu çıktıya bayt bayt eşit olduğunu sınar (sürüklenme bekçisi).

Kapsanan durumlar (spec §6.4/1): dolu ve boş sicil · eşik altı açılış turu (`null`) ·
mühürsüz maç (`closing: null`) · tek turlu maç · tam sayı değerli ondalık (`40.0`) ·
negatif hareket · HTML'de kaçış isteyen adlar (`&`, `'`) · Türkçe harfler · çıpa geride
(dolu) ve çıpa eşit (boş) · dışa aktarım anından önce ve sonra başlayan maçlar.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from football_edge.ledger import _canonical

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "web/fixtures"
FULL = FIXTURES / "snapshot.fixture.web-full.json"
EMPTY = FIXTURES / "snapshot.fixture.web-empty.json"
# The Odds API olay kimliğinin sabit uzunluklu öneki (spec §8.1). Uzunluk B-1'in
# `site/slugs.py` sabitidir; T10 `verify-snapshot` ile uzlaştırır.
PATH_ID_LENGTH = 12
HASHED_OUT = ("generated_at", "git_sha", "content_sha256")

Json = dict[str, Any]


def _hex(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _event_id(number: int) -> str:
    return hashlib.md5(f"fixture-match-{number}".encode()).hexdigest()


def content_sha256(document: Json) -> str:
    """Spec §5.2: `generated_at`, `git_sha` ve kendisi hariç gövdenin kanonik sha256'sı."""
    body = {key: value for key, value in document.items() if key not in HASHED_OUT}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _round(observed_at: str, books: int, home: float, draw: float, away: float) -> Json:
    return {"observed_at": observed_at, "books": books, "p": _triple(home, draw, away)}


def _triple(home: float, draw: float, away: float) -> Json:
    return {"home": home, "draw": draw, "away": away}


TEAMS = {
    "kz": ("Kuzeyspor", "kuzeyspor"),
    "gn": ("Güneyköy İdmanyurdu", "guneykoy-idmanyurdu"),
    "db": ("Doğu & Batı FK", "dogu-bati-fk"),
    "ob": ("O'Brien Rovers", "obrien-rovers"),
    "dc": ("Delta City", "delta-city"),
    "et": ("Epsilon Town", "epsilon-town"),
}


def _match(number: int, league: str, when: str, home: str, away: str, **rest: Any) -> Json:
    event = _event_id(number)
    (home_name, home_slug), (away_name, away_slug) = TEAMS[home], TEAMS[away]
    h2h = {"opening": rest["opening"], "latest": rest["latest"], "closing": rest["closing"]}
    return {
        "id": event,
        "league_id": league,
        "path_id": event[:PATH_ID_LENGTH],
        "slug": f"{home_slug}-vs-{away_slug}",
        "date": when[:10],
        "commence_time": when,
        "home": home_name,
        "away": away_name,
        "sealed": rest["sealed"],
        "rounds": rest["rounds"],
        "h2h": h2h,
        "move": rest["move"],
        "indexable": rest["indexable"],
    }


def _matches() -> list[Json]:
    close1 = _round("2026-09-19T13:45:00Z", 7, 48.3, 26.0, 25.7)
    close2 = _round("2026-09-20T16:15:00Z", 5, 38.0, 29.5, 32.5)
    close4 = _round("2026-09-22T19:30:00Z", 6, 28.9, 28.0, 43.1)
    only3 = _round("2026-09-23T06:00:00Z", 4, 36.1, 30.0, 33.9)
    close6 = _round("2026-09-23T16:45:00Z", 4, 42.5, 29.0, 28.5)
    matches = [
        _match(
            1,
            "xla.1",
            "2026-09-19T14:00:00Z",
            "kz",
            "gn",
            sealed=True,
            rounds=12,
            opening=_round("2026-09-16T06:00:00Z", 6, 45.7, 27.1, 27.2),
            latest=close1,
            closing=close1,
            move=_triple(2.6, -1.1, -1.5),
            indexable=True,
        ),
        # Açılış turunda 2 kitap: eşik altı → null; hareket de açılışsız → null.
        _match(
            2,
            "xla.1",
            "2026-09-20T16:30:00Z",
            "db",
            "ob",
            sealed=True,
            rounds=9,
            opening=None,
            latest=close2,
            closing=close2,
            move=None,
            indexable=True,
        ),
        # Tek tur, mühürsüz, dışa aktarım anından SONRA başlıyor.
        _match(
            3,
            "xla.1",
            "2026-09-26T18:00:00Z",
            "gn",
            "db",
            sealed=False,
            rounds=1,
            opening=only3,
            latest=only3,
            closing=None,
            move=None,
            indexable=False,
        ),
        _match(
            4,
            "xla.1",
            "2026-09-22T19:45:00Z",
            "ob",
            "kz",
            sealed=True,
            rounds=14,
            opening=_round("2026-09-19T06:00:00Z", 5, 30.2, 28.4, 41.4),
            latest=close4,
            closing=close4,
            move=_triple(-1.3, -0.4, 1.7),
            indexable=True,
        ),
        # Mühürsüz, iki turlu: hareket açılış→son.
        _match(
            5,
            "xla.1",
            "2026-09-27T13:00:00Z",
            "kz",
            "db",
            sealed=False,
            rounds=6,
            opening=_round("2026-09-21T06:00:00Z", 5, 51.0, 25.3, 23.7),
            latest=_round("2026-09-24T05:45:00Z", 5, 52.4, 24.9, 22.7),
            closing=None,
            move=_triple(1.4, -0.4, -1.0),
            indexable=True,
        ),
        # `40.0` / `30.0`: tam sayı değerli ondalık — JS `40` okur, biçim `40.0` basmalı.
        _match(
            6,
            "xlb.1",
            "2026-09-23T17:00:00Z",
            "dc",
            "et",
            sealed=True,
            rounds=5,
            opening=_round("2026-09-20T06:00:00Z", 3, 40.0, 30.0, 30.0),
            latest=close6,
            closing=close6,
            move=_triple(2.5, -1.0, -1.5),
            indexable=True,
        ),
    ]
    return sorted(matches, key=lambda match: (match["commence_time"], match["id"]))


def _leagues() -> list[Json]:
    return [
        {
            "id": "xla.1",
            "slug": "synthetic-league-alpha",
            "name": "Synthetic League Alpha",
            "country": "Testland",
            "matches": 5,
            "move_distribution": {"p10": 0.4, "p50": 1.8, "p90": 4.1},
        },
        {
            "id": "xlb.1",
            "slug": "synthetic-league-beta",
            "name": "Synthetic League Beta",
            "country": "Otherland",
            "matches": 1,
            "move_distribution": None,
        },
    ]


def _teams() -> list[Json]:
    counts = (
        ("xla.1", "kz", 3),
        ("xla.1", "gn", 2),
        ("xla.1", "db", 3),
        ("xla.1", "ob", 2),
        ("xlb.1", "dc", 1),
        ("xlb.1", "et", 1),
    )
    teams = [
        {
            "league_id": league,
            "slug": TEAMS[key][1],
            "name": TEAMS[key][0],
            "matches": count,
            "indexable": count >= 3,
        }
        for league, key, count in counts
    ]
    return sorted(teams, key=lambda team: (team["league_id"], team["slug"]))


def _full_record() -> Json:
    entries = [
        {
            "publication_id": 1,
            "match_id": _event_id(1),
            "market": "h2h",
            "outcome": "home",
            "published_at": "2026-09-18T09:00:00Z",
            "published_price": 2.2,
            "publication_ledger_id": 1201,
            "closing_fair_price": 2.07,
            "clv": 6.28,
            "publication_hash": _hex("fixture-publication-1"),
        },
        {
            "publication_id": 2,
            "match_id": _event_id(4),
            "market": "h2h",
            "outcome": "draw",
            "published_at": "2026-09-21T09:00:00Z",
            "published_price": 3.4,
            "publication_ledger_id": 1455,
            "closing_fair_price": 3.57,
            "clv": -4.76,
            "publication_hash": _hex("fixture-publication-2"),
        },
    ]
    summary = {"mean_clv": 0.76, "ci_low": -4.76, "ci_high": 6.28, "n": 2}
    return {"published": 2, "entries": entries, "summary": summary}


def _anchor(rows: int, last_id: int) -> Json:
    return {
        "file": "head-2026-09-24.txt",
        "rows": rows,
        "last_id": last_id,
        "head": _hex(f"fixture-head-{last_id}"),
    }


def build(*, full: bool) -> Json:
    document: Json = {
        "schema_version": 1,
        "generated_at": "2026-09-24T06:00:00Z",
        "git_sha": _hex("fixture-git")[:40],
        "content_sha256": "",
        "ledger": {
            "rows": 1834,
            "last_id": 1840,
            "head": _hex("fixture-head-1840"),
            "anchor": _anchor(1830, 1836) if full else _anchor(1834, 1840),
        },
        "floor": "2026-07-02T00:00:00Z",
        "leagues": _leagues(),
        "teams": _teams(),
        "matches": _matches(),
        "record": _full_record() if full else {"published": 0, "entries": [], "summary": None},
        "value_badge": None,
        "analysis": None,
    }
    document["content_sha256"] = content_sha256(document)
    return document


def render(document: Json) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def expected_files() -> dict[Path, str]:
    return {FULL: render(build(full=True)), EMPTY: render(build(full=False))}


def main() -> int:
    for path, text in expected_files().items():
        path.write_text(text, encoding="utf-8")
        sys.stdout.write(f"{path.relative_to(REPO)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
