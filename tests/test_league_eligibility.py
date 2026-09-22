"""İz A (2026-09-23) — N1/B1/AUT yapılandırmada, ama KREDİ HARCAMAZ.

The Odds API kredisi yalnız `active: true` liglerde harcanır: `collect snapshot`/`seal`
`active_leagues()`i, `fetch-results` de aynısını verir. Üç yeni lig `active: false` taşır;
etkinleştirme kullanıcı kararıdır (bütçe 500/ay). Bu dosya o anahtarın KAPALI olduğunu ve
kapalıyken gerçekten hiçbir ücretli isteğin atılmadığını uçtan uca sınar; bir de her
toplayıcının hangi liglere uygulandığını (TFF/stadyum/haber yalnız Türkiye).
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from football_edge import collect, fetch, rounds
from football_edge.collectors import footystats, news, results, tff, venues
from football_edge.collectors.footystats import FootyStatsResult
from football_edge.collectors.results import ResultsCollectResult
from football_edge.history.catalog import load_catalog
from football_edge.leagues import League, active_leagues, load_leagues
from tests.fake_db import FakeLedgerDb
from tests.payloads import quota_headers

REPO = Path(__file__).resolve().parents[1]
LEAGUES_PATH = REPO / "config/leagues.yaml"

LIVE_KEYS = (
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_turkey_super_league",
)

# Anahtarlar ölçüm belgesinden (docs/superpowers/specs/2026-09-22-faz2-olcumler-ve-
# kararlar.md §2.5, `/v4/sports?all=true`, 0 kredi) — tahmin değil. Footystats yolları
# 2026-09-23'te `collector._guarded_get` ile ölçüldü (200, `xg-all` tablosu 18/18/12 takım).
NEW_LEAGUES = (
    League(
        "ned.1",
        "soccer_netherlands_eredivisie",
        "Eredivisie",
        "Netherlands",
        "nl",
        "NL",
        False,
        "/netherlands/eredivisie/xg",
    ),
    League(
        "bel.1",
        "soccer_belgium_first_div",
        "First Division A",
        "Belgium",
        "nl",
        "BE",
        False,
        "/belgium/pro-league/xg",
    ),
    League(
        "aut.1",
        "soccer_austria_bundesliga",
        "Bundesliga",
        "Austria",
        "de",
        "AT",
        False,
        "/austria/bundesliga/xg",
    ),
)
NEW_KEYS = tuple(league.odds_api_key for league in NEW_LEAGUES)


def _configured() -> tuple[League, ...]:
    return load_leagues(LEAGUES_PATH)


def test_the_three_new_leagues_are_configured_after_the_live_six() -> None:
    assert _configured()[6:] == NEW_LEAGUES


def test_the_odds_spending_switch_is_off_for_the_new_leagues() -> None:
    """ANAHTAR: `active`. Açmak (true) snapshot + mühür kredisi harcar — kullanıcı kararı.
    Bu test kırmızıya dönerse biri anahtarı açmıştır: onay ve kredi hesabı raporda olmalı."""
    by_id = {league.id: league for league in _configured()}
    for league in NEW_LEAGUES:
        assert by_id[league.id].active is False, f"{league.id} kredi harcamaya açılmış"
    assert not set(NEW_KEYS) & {league.odds_api_key for league in active_leagues(_configured())}


def test_odds_keys_agree_with_the_history_catalog() -> None:
    """Canlı ve tarihsel katalog aynı ligi aynı The Odds API anahtarıyla adlandırmalı —
    yoksa canlı kapanış ile tarihsel kapanış farklı ligler üzerinden eşlenir."""
    catalog = {
        entry.league_id: entry
        for entry in load_catalog(REPO / "config/history_leagues.yaml").leagues
    }
    for league in _configured():
        assert league.id in catalog, f"{league.id} tarihsel katalogda yok"
        assert league.odds_api_key == catalog[league.id].odds_api_key, league.id


# ── Uçtan uca: anahtar kapalıyken ücretli istek ATILMAZ ─────────────────────


def _patch_main(monkeypatch: pytest.MonkeyPatch, db: FakeLedgerDb, requested: list[str]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path.split("/")[3])  # /v4/sports/<key>/odds
        return httpx.Response(200, json=[], headers=quota_headers(400))

    monkeypatch.setattr(collect, "LEAGUES_PATH", LEAGUES_PATH)
    monkeypatch.setattr(collect, "connect", lambda: db)
    real_client = httpx.Client
    monkeypatch.setattr(
        collect.httpx, "Client", lambda: real_client(transport=httpx.MockTransport(handler))
    )
    monkeypatch.setenv("ODDS_API_KEY", "TEST-KEY")


def test_snapshot_with_the_real_config_calls_only_the_six_live_keys(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = FakeLedgerDb()
    requested: list[str] = []
    _patch_main(monkeypatch, db, requested)

    assert collect.main(["snapshot"]) == 0

    capsys.readouterr()
    assert tuple(requested) == LIVE_KEYS
    # Ayna tüm yapılandırmayı taşır (yabancı anahtar için) — `active` bayrağıyla birlikte.
    assert {league_id: row[6] for league_id, row in db.leagues.items() if row[6] is False} == {
        "ned.1": False,
        "bel.1": False,
        "aut.1": False,
    }


def test_seal_with_the_real_config_never_calls_an_inactive_league(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Mühür yalnız penceresinde maç olan ligi çağırır; o maç bir pasif lige aitse bile
    (ör. elle eklenmiş) ücretli çağrı atılmaz."""
    soon = datetime.now(UTC) + timedelta(minutes=10)
    db = FakeLedgerDb(
        leagues={"ned.1": ("ned.1",), "tur.1": ("tur.1",)},
        matches={
            "evt_ned": {"league_id": "ned.1", "commence_time": soon, "sealed_at": None},
            "evt_tur": {"league_id": "tur.1", "commence_time": soon, "sealed_at": None},
        },
    )
    requested: list[str] = []
    _patch_main(monkeypatch, db, requested)

    code = collect.main(["seal"])

    capsys.readouterr()
    assert code == 0
    assert requested == ["soccer_turkey_super_league"]


def test_fetch_results_with_the_real_config_asks_only_the_six_live_leagues(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`/scores` de ücretli (2 kredi/çağrı, `daysFrom`); bugün hiçbir zamanlayıcı çağırmıyor."""
    monkeypatch.setattr(fetch, "LEAGUES_PATH", LEAGUES_PATH)
    monkeypatch.setenv("ODDS_API_KEY", "TEST-KEY")
    seen: list[tuple[str, ...]] = []

    def fake_collect_results(
        conn: object, client: object, api_key: str, leagues: tuple[League, ...], now: object
    ) -> ResultsCollectResult:
        seen.append(tuple(league.odds_api_key for league in leagues))
        return ResultsCollectResult(written=0, failed_leagues=(), scoreless_completed=())

    monkeypatch.setattr(fetch, "collect_results", fake_collect_results)

    assert fetch._fetch_results_command(object(), object(), datetime.now(UTC)) == 0

    capsys.readouterr()
    assert seen == [LIVE_KEYS]


def test_fetch_footystats_with_the_real_config_asks_only_the_active_leagues_paths(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """I1 (inceleme): `fetch-footystats` komutunun kendisi pasif ligi süzmeli. Süzmezse Mac'teki
    launchd işi `config/sources.yaml`de BEYAN EDİLMEMİŞ yolları ister — kapı bunu görmezdi."""
    monkeypatch.setattr(fetch, "LEAGUES_PATH", LEAGUES_PATH)
    seen: list[tuple[str | None, ...]] = []

    def fake_collect_footystats(
        conn: object, client: object, leagues: tuple[League, ...], **_: object
    ) -> FootyStatsResult:
        seen.append(tuple(league.footystats_path for league in leagues))
        return FootyStatsResult(written=0, failed_leagues=())

    monkeypatch.setattr(fetch, "collect_footystats", fake_collect_footystats)

    assert fetch._fetch_footystats_command(object(), object(), datetime.now(UTC)) == 0

    capsys.readouterr()
    assert seen == [tuple(league.footystats_path for league in active_leagues(_configured()))]
    assert not {league.footystats_path for league in NEW_LEAGUES if not league.active} & set(
        seen[0]
    )


# ── Toplayıcı başına uygunluk ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "collector",
    [footystats.collect_footystats, results.collect_results, rounds.run_snapshot, rounds.run_seal],
)
def test_league_looping_collectors_take_the_configured_league_set(collector: object) -> None:
    """Bu dördü `config/leagues.yaml`den gelen lig kümesini döngüler: yeni lig onlara
    `active: true` (+ footystats için `footystats_path`) ile girer."""
    assert "leagues" in inspect.signature(collector).parameters  # type: ignore[arg-type]


@pytest.mark.parametrize("collector", [tff.collect_tff, venues.collect_venues, news.collect_news])
def test_turkey_only_collectors_do_not_take_a_league_set(collector: object) -> None:
    """TFF tek ulusal sayfa (Türk ligleri), stadyum listesi sabit Türk kulüpleri, haber
    kaynakları Türkçe: lig eklemek bunları HİÇ etkilemez — N1/B1/AUT'a uygulanmazlar."""
    assert "leagues" not in inspect.signature(collector).parameters  # type: ignore[arg-type]


def test_venues_cover_only_turkish_clubs() -> None:
    assert tuple(spec.home_team for spec in venues.VENUES) == ("Galatasaray",)
