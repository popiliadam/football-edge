from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.results import MatchOutcome, fetch_scores, parse_scores, write_results

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
FIXTURE = Path("tests/fixtures/results/scores_sample.json")


def event(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "evt1",
        "sport_key": "soccer_turkey_super_league",
        "commence_time": "2026-09-18T18:00:00Z",
        "completed": True,
        "home_team": "Galatasaray",
        "away_team": "Fenerbahce",
        "scores": [
            {"name": "Galatasaray", "score": "2"},
            {"name": "Fenerbahce", "score": "1"},
        ],
        "last_update": "2026-09-18T20:00:00Z",
    }
    return {**base, **overrides}


def fixture_payload() -> list[dict[str, Any]]:
    return list(json.loads(FIXTURE.read_text(encoding="utf-8")))


# ── parse_scores ─────────────────────────────────────────────────────────────


def test_maps_scores_to_home_and_away_by_name() -> None:
    """`scores` dizisinin SIRASI garanti değildir; ada göre eşlenir, konuma göre değil."""
    reversed_order = event(
        scores=[{"name": "Fenerbahce", "score": "1"}, {"name": "Galatasaray", "score": "2"}]
    )
    (outcome,) = parse_scores([reversed_order], NOW)
    assert (outcome.home_goals, outcome.away_goals) == (2, 1)


def test_skips_events_that_have_not_completed() -> None:
    assert parse_scores([event(completed=False, scores=None)], NOW) == ()


def test_skips_a_not_completed_event_even_when_it_already_carries_scores() -> None:
    """`test_skips_events_that_have_not_completed` TEK BAŞINA `completed` kontrolünü
    KANITLAMAZ: o testteki olay `scores=None` de taşıyor, yani `if not scores: continue`
    aynı satırı `completed` kontrolü hiç var olmasa bile atlardı (ÖLÇÜLDÜ: `completed`
    filtresi tamamen silinip yalnız o testle koşulduğunda paket YEŞİL kalıyordu — bu tam
    olarak projenin 'kırılamayan test' korkusu). Bu test, canlı bir skorla (maç henüz
    bitmemiş olsa bile API bazen ara sonucu taşıyabilir) `completed=False`ı TEK BAŞINA
    izole eder.
    """
    live_but_unfinished = event(completed=False)
    assert parse_scores([live_but_unfinished], NOW) == ()


def test_unknown_team_name_in_scores_raises() -> None:
    """Skor adı takım adlarından biriyle eşleşmiyorsa SESSİZCE 0-0 yazmak felakettir."""
    mismatched = [{"name": "Besiktas", "score": "2"}, {"name": "Fenerbahce", "score": "1"}]
    with pytest.raises(ContractViolation, match="eşleşmedi"):
        parse_scores([event(scores=mismatched)], NOW)


def test_non_numeric_score_raises() -> None:
    with pytest.raises(ContractViolation, match="sayı"):
        parse_scores(
            [
                event(
                    scores=[
                        {"name": "Galatasaray", "score": "-"},
                        {"name": "Fenerbahce", "score": "1"},
                    ]
                )
            ],
            NOW,
        )


def test_match_id_is_the_odds_api_event_id() -> None:
    """Sonuç yolu varlık eşlemesi GEREKTİRMEZ: aynı event_id zaten matches tablosunda."""
    (outcome,) = parse_scores([event()], NOW)
    assert outcome.match_id == "evt1"


def test_empty_payload_returns_empty_tuple() -> None:
    assert parse_scores([], NOW) == ()


def test_parses_only_completed_events_from_a_mixed_payload() -> None:
    """Tek turda hem tamamlanmış hem tamamlanmamış maç gelebilir; yalnız ilki sonuç üretir.

    İkinci olay BİLİNÇLİ olarak `scores` taşıyor (`completed=False` olsa bile): aksi
    hâlde bu test yalnız `if not scores: continue` dalını sınar, `completed` kontrolünü
    değil — bkz. `test_skips_a_not_completed_event_even_when_it_already_carries_scores`.
    """
    incomplete = event(id="evt2", completed=False)
    outcomes = parse_scores([event(), incomplete], NOW)
    assert [o.match_id for o in outcomes] == ["evt1"]


def test_completed_event_with_null_scores_is_skipped_not_raised() -> None:
    """BUGÜNKÜ davranış: completed=true + scores=None de sessizce atlanır (Adım 2 kodunun
    aynen taşınmış hâli). Vantor sözleşmesi tamamlanmış bir maçın skor taşımasını ima eder;
    bu test o varsayım kırılırsa (vantor bir gün completed=true + scores=null döndürürse)
    davranışın SESSİZ KALDIĞINI görünür kılıp kilitliyor — bkz. task-9-report.md 'concerns'.
    """
    assert parse_scores([event(scores=None)], NOW) == ()


def test_observed_at_is_stamped_on_every_outcome() -> None:
    other_time = datetime(2026, 9, 19, 18, 30, tzinfo=UTC)
    (outcome,) = parse_scores([event()], other_time)
    assert outcome.observed_at == other_time


# ── parse_scores: kaydedilmiş fixture üzerinde sözleşme iddiaları (contract) ─────────────


@pytest.mark.contract
def test_parses_every_completed_event_in_the_fixture() -> None:
    outcomes = parse_scores(fixture_payload(), NOW)
    assert len(outcomes) == 4, f"fixture 4 tamamlanmış maç taşıyor; {len(outcomes)} ayrıştırıldı"


@pytest.mark.contract
def test_contract_goals_are_within_a_plausible_range() -> None:
    """0-15 makul üst sınır: ayrıştırıcının yanlış alanı/sütunu okuduğunu yakalar."""
    outcomes = parse_scores(fixture_payload(), NOW)
    for outcome in outcomes:
        assert 0 <= outcome.home_goals <= 15
        assert 0 <= outcome.away_goals <= 15


@pytest.mark.contract
def test_contract_match_id_is_the_fixtures_event_id_with_no_translation() -> None:
    """Sonuç yolu varlık eşlemesi gerektirmez: match_id fixture'daki 'id' ile BİREBİR
    aynı kalmalı — hiçbir dönüşüm/normalizasyon geçmemeli."""
    fixture_ids = {str(entry["id"]) for entry in fixture_payload() if entry["completed"]}
    outcomes = parse_scores(fixture_payload(), NOW)
    assert {outcome.match_id for outcome in outcomes} == fixture_ids


# ── fetch_scores ──────────────────────────────────────────────────────────────


def _score_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": "evt1",
            "sport_key": "soccer_turkey_super_league",
            "commence_time": "2026-09-18T18:00:00Z",
            "completed": True,
            "home_team": "Galatasaray",
            "away_team": "Fenerbahce",
            "scores": [
                {"name": "Galatasaray", "score": "2"},
                {"name": "Fenerbahce", "score": "1"},
            ],
            "last_update": "2026-09-18T20:00:00Z",
        }
    ]


def test_fetch_scores_builds_request_and_returns_outcomes_and_quota() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json=_score_payload(),
            headers={
                "x-requests-remaining": "480",
                "x-requests-used": "20",
                "x-requests-last": "2",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    outcomes, quota = fetch_scores(client, "KEY", "soccer_turkey_super_league", NOW, days_from=3)

    assert len(outcomes) == 1
    assert outcomes[0].match_id == "evt1"
    assert quota.remaining == 480
    assert quota.last_cost == 2, "daysFrom belirtilince maliyet 2 kredidir (belgelenmiş)"

    parsed = urlparse(str(captured["url"]))
    assert parsed.path == "/v4/sports/soccer_turkey_super_league/scores/"
    params = parse_qs(parsed.query)
    assert params["apiKey"] == ["KEY"]
    assert params["daysFrom"] == ["3"]
    assert params["dateFormat"] == ["iso"]


def test_fetch_scores_defaults_days_from_to_three() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json=[],
            headers={
                "x-requests-remaining": "499",
                "x-requests-used": "1",
                "x-requests-last": "2",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch_scores(client, "KEY", "soccer_epl", NOW)

    params = parse_qs(urlparse(str(captured["url"])).query)
    assert params["daysFrom"] == ["3"]


@pytest.mark.parametrize("days_from", [0, 4, -1])
def test_fetch_scores_rejects_days_from_outside_one_to_three(days_from: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=[])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="daysFrom"):
        fetch_scores(client, "KEY", "soccer_epl", NOW, days_from=days_from)

    assert calls == 0, "geçersiz daysFrom için istek ATILMAMALI — kredi boşuna harcanır"


def test_fetch_scores_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "invalid key"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_scores(client, "BAD", "soccer_epl", NOW)


# ── write_results ─────────────────────────────────────────────────────────────


def outcome(
    match_id: str, observed_at: datetime = NOW, *, home: int = 2, away: int = 1
) -> MatchOutcome:
    return MatchOutcome(
        match_id=match_id,
        home_goals=home,
        away_goals=away,
        completed=True,
        observed_at=observed_at,
    )


class _PoisonConn:
    """`.cursor()` çağrılırsa patlar: boş demet veritabanına hiç DOKUNMAMALI."""

    def cursor(self) -> Any:
        raise AssertionError("write_results boş demet için veritabanına dokunmamalıydı")


@dataclass
class _FakeResultsDb:
    """`match_results` INSERT'ini taklit eder: yabancı anahtarı (matches) VE birincil
    anahtarı (match_id, observed_at) GERÇEKTEN uygular — fake_db.py'deki "taklit şemanın
    yük taşıyan kısıtlarını uygular" ilkesiyle aynı gerekçe.

    `rowcount`, psycopg3'ün `executemany` sonrası her alt ifadenin PostgreSQL'in bildirdiği
    GERÇEK etkilenen satır sayısını (`command_tuples`) TOPLADIĞI varsayımını modelliyor —
    ifade SAYISINI değil. Bu proje zaten `db.py:upsert_matches`te `executemany` +
    `max(cur.rowcount, 0)` kullanıyor; farkı oradaki HER ifadenin `DO UPDATE` olduğu için
    her zaman 1 satırı etkilemesi. Burada `WHERE EXISTS` / `ON CONFLICT DO NOTHING` bazı
    ifadeleri 0'a düşürebilir. Bu varsayım CANLI Postgres'e karşı DOĞRULANMADI (bu ortamda
    DATABASE_URL yok) — bkz. task-9-report.md 'concerns'.
    """

    matches: frozenset[str] = frozenset()
    results: dict[tuple[str, str], tuple[int, int, bool]] = field(default_factory=dict)
    statements: list[str] = field(default_factory=list)

    def cursor(self) -> _FakeResultsCursor:
        return _FakeResultsCursor(self)

    def __enter__(self) -> _FakeResultsDb:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _FakeResultsCursor:
    def __init__(self, db: _FakeResultsDb) -> None:
        self._db = db
        self.rowcount = -1

    def __enter__(self) -> _FakeResultsCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def executemany(self, sql: str, params_seq: list[tuple[Any, ...]]) -> None:
        text = " ".join(sql.split())
        self._db.statements = [*self._db.statements, text]
        if not text.startswith("INSERT INTO match_results"):
            raise AssertionError(f"taklit bu toplu ifadeyi tanımıyor: {text}")
        affected = 0
        for match_id, observed_at, home, away, completed, fk_match_id in params_seq:
            if fk_match_id not in self._db.matches:
                continue  # WHERE EXISTS: matches'te olmayan maç sessizce düşer
            key = (match_id, observed_at)
            if key in self._db.results:
                continue  # ON CONFLICT (match_id, observed_at) DO NOTHING
            self._db.results[key] = (home, away, completed)
            affected += 1
        self.rowcount = affected


def test_write_results_returns_zero_for_empty_tuple_without_touching_the_db() -> None:
    assert write_results(_PoisonConn(), ()) == 0  # type: ignore[arg-type]


def test_write_results_drops_rows_for_matches_not_in_the_matches_table() -> None:
    """`/scores` bu projenin hiç oran toplamadığı maçları da döndürebilir — o satırlar
    HATA VERMEDEN düşmeli, tüm batch'i patlatmamalı."""
    db = _FakeResultsDb(matches=frozenset({"evt1"}))

    written = write_results(db, (outcome("evt1"), outcome("evt-unknown")))  # type: ignore[arg-type]

    assert written == 1
    assert ("evt1", "2026-09-19T12:00:00+00:00") in db.results
    assert all(key[0] != "evt-unknown" for key in db.results)


def test_write_results_is_idempotent_for_the_same_observation() -> None:
    db = _FakeResultsDb(matches=frozenset({"evt1"}))

    first = write_results(db, (outcome("evt1"),))  # type: ignore[arg-type]
    second = write_results(db, (outcome("evt1"),))  # type: ignore[arg-type]

    assert (first, second) == (1, 0)


def test_write_results_records_a_correction_as_a_new_row_at_a_new_observed_at() -> None:
    """Sonuçlar GÖZLEMDİR: düzeltilmiş skor eski satırın YERİNE geçmez, YANINA eklenir."""
    db = _FakeResultsDb(matches=frozenset({"evt1"}))
    later = datetime(2026, 9, 19, 15, 0, tzinfo=UTC)

    write_results(db, (outcome("evt1", NOW, home=2, away=1),))  # type: ignore[arg-type]
    written = write_results(db, (outcome("evt1", later, home=2, away=2),))  # type: ignore[arg-type]

    assert written == 1
    assert len(db.results) == 2, "düzeltme eskiyi EZMEMELİ, yeni bir satır olmalı"


def test_write_results_uses_a_single_batched_statement() -> None:
    db = _FakeResultsDb(matches=frozenset({f"evt{i}" for i in range(10)}))

    write_results(db, tuple(outcome(f"evt{i}") for i in range(10)))  # type: ignore[arg-type]

    inserts = [s for s in db.statements if s.startswith("INSERT INTO match_results")]
    assert len(inserts) == 1, "10 sonuç için TEK toplu ifade beklenir, satır başına değil"


def test_write_results_sql_declares_the_foreign_key_guard_and_conflict_clause() -> None:
    """Taklit (`_FakeResultsCursor`) FK/PK kısıtını SQL METNİNDEN BAĞIMSIZ, kendi Python
    mantığıyla uyguluyor (bkz. sınıf docstring'i) — yani gerçek ifadeden `WHERE EXISTS`
    ya da `ON CONFLICT` silinse bile yukarıdaki davranış-temelli testler YEŞİL kalırdı.
    Aynı gerekçeyle `db.py`de `test_insert_snapshots_sql_declares_ordinality_and_order_by`
    var: taklidin GÖRMEDİĞİ bir garanti, SQL METNİ üzerinden AYRICA doğrulanır.
    """
    db = _FakeResultsDb(matches=frozenset({"evt1"}))

    write_results(db, (outcome("evt1"),))  # type: ignore[arg-type]

    (statement,) = db.statements
    assert "WHERE EXISTS (SELECT 1 FROM matches WHERE id = %s)" in statement
    assert "ON CONFLICT (match_id, observed_at) DO NOTHING" in statement
