from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from football_edge import mapping
from football_edge.jev import NO_MATCH, ChoiceAnswer
from football_edge.mapping import (
    Resolution,
    candidates,
    canonical_team_names,
    resolve,
    resolve_source_aliases,
    write_aliases,
)
from tests.fake_jev import FakeJev
from tests.fake_obs_db import FakeObservationDb

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
CANONICAL = ("Galatasaray", "Fenerbahce", "Besiktas", "Gaziantep FK", "Trabzonspor")


def answer(choice: str, confidence: float) -> ChoiceAnswer:
    return ChoiceAnswer(choice=choice, confidence=confidence, probabilities={choice: confidence})


def test_candidates_are_narrowed_before_the_model_is_asked() -> None:
    """Kod aday çıkarır, Jev seçer (spec §5.3). Tüm listeyi sormak hem pahalı hem gürültülü."""
    narrowed = candidates("Galatasaray A.Ş.", CANONICAL, limit=3)
    assert "Galatasaray" in narrowed
    assert len(narrowed) <= 3


def test_candidates_never_omit_a_plausible_match() -> None:
    """Model, listeye KONULMAYAN bir değeri seçemez (TypeSafe Choice dokümanı).

    `CANONICAL` yalnız 5 kayıt taşıyor — `limit`in varsayılanından (8) KÜÇÜK. Brief'in
    verdiği orijinal hâliyle (`candidates("...", CANONICAL)`, limit override'sız) bu
    test HİÇBİR ZAMAN kırmızı veremezdi: `candidates()` ne yaparsa yapsın (SIRALAMASIZ,
    hatta TERS sıralı bile) 5 kaydın hepsi zaten döner, "eksik" hiç oluşamaz. Ölçüldü:
    sıralama `reverse=True`den `reverse=False`e çevrildiğinde (en kötü eşleşme önce)
    bu test YİNE GEÇTİ (report'ta kanıtlı). Burada `limit` aday havuzundan KÜÇÜK
    tutulur ki GERÇEK kırpma olsun ve "Gaziantep FK" GERÇEKTEN elenebilsin.
    """
    noisy_pool = CANONICAL + ("Real Madrid", "Bayern Munich", "Inter Milan", "Ajax", "Porto")
    narrowed = candidates("Gaziantep Futbol Kulübü", noisy_pool, limit=3)
    assert "Gaziantep FK" in narrowed
    assert len(narrowed) == 3, "limit havuzdan küçük tutuldu — kırpma gerçekten olmalı"


def test_high_confidence_match_is_accepted() -> None:
    """`"Galatasaray Istanbul"` KASITLI: `"Galatasaray A.Ş."` `normalise_team`in kurumsal
    ek listesindeki `a\\.?ş\\.?`ye birebir çarpar ve `resolve` modele hiç SORMADAN
    birebir-eşleşme dalına düşer (bkz. `test_exact_normalised_match_skips_the_model_
    entirely`) — bu test o zaman `FakeJev`i HİÇ ÇAĞIRMADAN "geçer" ve adının vaat
    ettiğini (yüksek güvenli bir MODEL cevabının kabulü) ölçmez. Ölçüldü: brief'in
    verdiği orijinal alias'la `client.seen == []` — bu dosyanın report'unda kanıtlıdır.
    """
    client = FakeJev(answer("Galatasaray", 0.97))
    found = resolve("Galatasaray Istanbul", CANONICAL, client, league="tur.1")
    assert found.canonical_id == "Galatasaray"
    assert client.seen != [], "birebir eşleşmeye düştü — bu test modeli hiç çağırmadı"


def test_low_confidence_match_is_refused_and_named() -> None:
    """Eşik altı eşleşme YAZILMAZ. Bir eşleşmeyi atlamak, yanlış eşlemekten iyidir."""
    client = FakeJev(answer("Fenerbahce", 0.41))
    found = resolve("FB A.Ş.", CANONICAL, client, league="tur.1", threshold=0.75)
    assert found.canonical_id is None
    assert "eşik" in found.reason


def test_no_match_option_is_offered_and_honoured() -> None:
    """Liste her girdiyi kapsamayabilir; 'hiçbiri' seçeneği olmadan model UYDURMAK zorunda kalır."""
    client = FakeJev(answer(NO_MATCH, 0.99))
    found = resolve("Panathinaikos", CANONICAL, client, league="tur.1")
    assert found.canonical_id is None
    assert NO_MATCH in client.seen[0]["criteria"]


def test_league_context_reaches_the_model() -> None:
    """Aynı ad farklı liglerde farklı kulüp olabilir; lig bağlamsız soru eksik sorudur.

    Alias `"Galatasaray Istanbul"` — bkz. `test_high_confidence_match_is_accepted`in
    docstring'i: `"Galatasaray A.Ş."` birebir eşleşmeye düşer ve `client.seen` HİÇ
    dolmaz, bu test de IndexError ile KIRMIZI verir (ölçüldü, report'ta kanıtlı).
    """
    client = FakeJev(answer("Galatasaray", 0.9))
    resolve("Galatasaray Istanbul", CANONICAL, client, league="tur.1")
    assert client.seen[0]["state"]["league"] == "tur.1"


def test_exact_normalised_match_skips_the_model_entirely() -> None:
    """Deterministik cevabı modele sormak hem para hem gürültüdür (spec §5.2 tasarım kuralı)."""
    client = FakeJev(answer("YANLIS", 1.0))
    found = resolve("  GALATASARAY  ", CANONICAL, client, league="tur.1")
    assert found.canonical_id == "Galatasaray"
    assert client.seen == [], "birebir eşleşmede model çağrıldı"


# ---------------------------------------------------------------------------
# write_aliases — brief'in verdiği kodda testsiz kalmıştı, burada eklenir.
# Gerçek psycopg yerine minimal bir taklit: yalnız `executemany`/`commit`in NE ile
# çağrıldığını kaydeder, bir SQL motoru değildir (bu dosyanın diğer testleriyle aynı
# ölçek: `mapping.py`nin SQL'i doğru ÜRETTİĞİNİ kanıtlar, Postgres'in onu doğru
# ÇALIŞTIRDIĞINI değil — o örtülü güven bu kod tabanının her yerinde aynıdır).
# ---------------------------------------------------------------------------


class _FakeAliasCursor:
    def __init__(self, conn: _FakeAliasConn) -> None:
        self._conn = conn

    def __enter__(self) -> _FakeAliasCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def executemany(self, sql: str, params_seq: list[tuple[Any, ...]]) -> None:
        self._conn.executed.append((" ".join(sql.split()), list(params_seq)))


@dataclass
class _FakeAliasConn:
    executed: list[tuple[str, list[tuple[Any, ...]]]] = field(default_factory=list)
    commits: int = 0

    def cursor(self) -> _FakeAliasCursor:
        return _FakeAliasCursor(self)

    def commit(self) -> None:
        self.commits += 1


def test_write_aliases_writes_only_resolved_entries_and_returns_their_count() -> None:
    conn = _FakeAliasConn()
    resolved = Resolution("Galatasaray A.Ş.", "Galatasaray", 0.97, "model seçti")
    unresolved = Resolution("Panathinaikos", None, 0.99, "model 'hiçbiri' dedi")

    written = write_aliases(conn, "footystats", "team", (resolved, unresolved), NOW)

    assert written == 1
    [(sql, params)] = conn.executed
    assert "INSERT INTO entity_aliases" in sql
    assert "ON CONFLICT (source_id, entity_kind, alias) DO UPDATE" in sql
    assert params == [("footystats", "team", "Galatasaray A.Ş.", "Galatasaray", 0.97, NOW)]
    assert conn.commits == 1


def test_write_aliases_skips_the_database_entirely_when_nothing_resolved() -> None:
    """Boş yazım denenmez: `executemany`/`commit` hiç çağrılmamalı, 0 yeniden hesaplanmamalı."""
    conn = _FakeAliasConn()
    unresolved = Resolution("Panathinaikos", None, 0.99, "model 'hiçbiri' dedi")

    written = write_aliases(conn, "footystats", "team", (unresolved,), NOW)

    assert written == 0
    assert conn.executed == []
    assert conn.commits == 0


# ---------------------------------------------------------------------------
# canonical_team_names — `matches` tablosundan lig-sınırlı kanonik ad okuma.
# ---------------------------------------------------------------------------


class _FakeMatchesCursor:
    def __init__(self, conn: _FakeMatchesConn) -> None:
        self._conn = conn

    def __enter__(self) -> _FakeMatchesCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self._conn.seen_sql.append(" ".join(sql.split()))
        self._conn.seen_params.append(params)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._conn.rows)


@dataclass
class _FakeMatchesConn:
    rows: tuple[tuple[Any, ...], ...]
    seen_sql: list[str] = field(default_factory=list)
    seen_params: list[tuple[Any, ...]] = field(default_factory=list)

    def cursor(self) -> _FakeMatchesCursor:
        return _FakeMatchesCursor(self)


def test_canonical_team_names_dedupes_and_sorts_and_scopes_by_league() -> None:
    """`home_team`/`away_team` aynı takımı iki kez taşıyabilir (ev/deplasman) — tekilleşir."""
    conn = _FakeMatchesConn(rows=(("Galatasaray",), ("Fenerbahce",), ("Galatasaray",)))

    found = canonical_team_names(conn, "tur.1")

    assert found == ("Fenerbahce", "Galatasaray")
    assert conn.seen_params == [("tur.1", "tur.1")], "league_id İKİ yarıya da (home/away) geçmeli"
    assert "WHERE league_id = %s" in conn.seen_sql[0]


def test_canonical_team_names_is_empty_when_the_league_has_no_matches() -> None:
    conn = _FakeMatchesConn(rows=())

    assert canonical_team_names(conn, "tur.9") == ()


# ---------------------------------------------------------------------------
# _alias_text
# ---------------------------------------------------------------------------


def test_alias_text_returns_the_team_name_field() -> None:
    assert mapping._alias_text({"team_name": "Galatasaray"}, "footystats") == "Galatasaray"


def test_alias_text_names_the_source_when_the_field_is_missing() -> None:
    """Sessizce atlamak yerine adıyla patlar — bağlanmamış bir kaynak "0 eşleşme, her şey
    yolunda" gibi görünmesin diye (below-threshold-bile RAPORLANIR ilkesiyle aynı ruh)."""
    with pytest.raises(RuntimeError, match="team_name"):
        mapping._alias_text({"club": "Galatasaray"}, "some-future-source")


# ---------------------------------------------------------------------------
# resolve_source_aliases — `latest_observations` GERÇEK (tests/fake_obs_db.py, zaten
# kendi testinde kanıtlı), `write_aliases` monkeypatch'lenir (kendi testi yukarıda) —
# bu fonksiyonun İŞİ yalnız "lig önekine göre süz, resolve'u çağır, yazdır".
# ---------------------------------------------------------------------------


def _seed_team_observation(db: FakeObservationDb, entity_key: str, team_name: str) -> None:
    db.rows = [
        *db.rows,
        {
            "source_id": "footystats",
            "entity_kind": "team",
            "entity_key": entity_key,
            "observed_at": NOW,
            "payload": {"team_name": team_name},
            "content_hash": f"hash-{entity_key}",
        },
    ]


def test_resolve_source_aliases_filters_by_league_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeObservationDb()
    _seed_team_observation(db, "tur.1:1", "Galatasaray Istanbul")
    _seed_team_observation(db, "tur.2:9", "Bu Lig Dışında Kalmalı")
    recorded: list[tuple[Resolution, ...]] = []
    monkeypatch.setattr(
        mapping,
        "write_aliases",
        lambda conn, source, kind, resolutions, now: (recorded.append(resolutions), 1)[1],
    )
    client = FakeJev(answer("Galatasaray", 0.9))

    report = resolve_source_aliases(db, client, "footystats", "tur.1", CANONICAL, NOW)

    assert report is not None
    assert report.written == 1
    assert [entry.alias for entry in report.resolutions] == ["Galatasaray Istanbul"]
    [recorded_resolutions] = recorded
    assert [entry.alias for entry in recorded_resolutions] == ["Galatasaray Istanbul"]


def test_resolve_source_aliases_returns_none_when_no_observation_matches_the_league(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boş girişte `write_aliases` HİÇ çağrılmamalı — DB'ye boş bir tur için dokunulmaz."""
    db = FakeObservationDb()
    _seed_team_observation(db, "tur.2:9", "Başka Lig")
    monkeypatch.setattr(
        mapping,
        "write_aliases",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("write_aliases ÇAĞRILMAMALIYDI")),
    )

    report = resolve_source_aliases(
        db, FakeJev(answer("Galatasaray", 0.9)), "footystats", "tur.1", CANONICAL, NOW
    )

    assert report is None
