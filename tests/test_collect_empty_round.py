"""Boş tur bekçisi: her lig boşken ufukta fikstür varsa snapshot turu yeşil kalamaz.

2026-09-23 ölçümü: FIFA arasında 8 ligin hepsi `yazılacak satır yok` dedi, kredi değişmedi, tur
YEŞİL. Ara için doğru — ama sessiz bir arıza (anahtar adı değişti, API boş dönüyor, bölge
değişti) bayt bayt aynı görünür ve canlı gölge günlerce karar almaz. İkisini ücretsiz `/events`
ucu ayırır: ufukta fikstür yoksa ara, varsa arıza.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from football_edge import collect
from tests.fake_db import FakeLedgerDb
from tests.payloads import event, quota_headers
from tests.test_collect_main import _db_due_for_seal, _patch_main

LEAGUES_YAML = """
leagues:
  - id: eng.1
    odds_api_key: soccer_epl
    name: EPL
    country: England
    lang: en
    gl: GB
    active: true
    footystats_path: /eng/xg
  - id: tur.1
    odds_api_key: soccer_turkey_super_league
    name: Süper Lig
    country: Turkey
    lang: tr
    gl: TR
    active: true
    footystats_path: /tur/xg
"""

EMPTY_ROUND_LINE = "oran boş ama ufukta fikstür var"
# `/events` de kredi başlıklarını taşır; `x-requests-last: 0` ölçülen değerdir.
FREE_HEADERS = {**quota_headers(400), "x-requests-last": "0"}

Handler = Callable[[httpx.Request], httpx.Response]


def _kickoff(days: float) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fixture(sport_key: str, commence_time: str) -> dict[str, str]:
    return {
        "id": f"{sport_key}-1",
        "sport_key": sport_key,
        "sport_title": sport_key,
        "commence_time": commence_time,
        "home_team": "A",
        "away_team": "B",
    }


def _api(
    seen: list[httpx.Request],
    *,
    odds: dict[str, httpx.Response] | None = None,
    fixtures: dict[str, list[dict[str, str]]] | None = None,
    events_status: int = 200,
) -> Handler:
    """`/odds` varsayılanı boş liste (milli ara ya da sessiz arıza — ikisi aynı görünür);
    `/events` varsayılanı fikstürsüz. Her istek sırasıyla `seen`e düşer."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        sport_key = request.url.path.split("/")[3]
        if request.url.path.endswith("/events"):
            if events_status != 200:
                return httpx.Response(events_status, json={"message": "down"})
            return httpx.Response(
                200, json=(fixtures or {}).get(sport_key, []), headers=FREE_HEADERS
            )
        return (odds or {}).get(sport_key) or httpx.Response(
            200, json=[], headers=quota_headers(400)
        )

    return handler


def _run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, handler: Handler, command: str = "snapshot"
) -> int:
    db = FakeLedgerDb()
    _patch_main(monkeypatch, tmp_path, db, handler)
    (tmp_path / "leagues.yaml").write_text(LEAGUES_YAML, encoding="utf-8")
    return collect.main([command])


def _events_calls(seen: list[httpx.Request]) -> list[str]:
    return [request.url.path for request in seen if request.url.path.endswith("/events")]


def test_an_all_empty_round_with_fixtures_in_the_horizon_is_red_and_names_the_leagues(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """(a) Oran yok, fikstür var: sessiz arıza. Yalnız fikstürü olan lig adlandırılır."""
    seen: list[httpx.Request] = []
    handler = _api(seen, fixtures={"soccer_epl": [_fixture("soccer_epl", _kickoff(2))]})

    code = _run(monkeypatch, tmp_path, handler)

    out = capsys.readouterr().out
    errors = [record.getMessage() for record in caplog.records if record.levelname == "ERROR"]
    assert code == collect.EXIT_EMPTY_ROUND == 19
    assert f"{EMPTY_ROUND_LINE}: eng.1" in out, f"rapor ligi adlandırmıyor: {out!r}"
    assert any(f"{EMPTY_ROUND_LINE}: eng.1" in message for message in errors), (
        f"ERROR logu yok ya da ligi adlandırmıyor: {errors}"
    )
    assert all("tur.1" not in message for message in errors), "fikstürü olmayan lig de adlandırıldı"


def test_an_international_break_stays_green(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """(b) Ölçülen ara: sonraki fikstür 16 gün sonra, 7 günlük ufkun DIŞINDA → exit 0.

    Fikstür bilerek ufkun dışında döndürülür: API `commenceTimeTo`yu uygulamasa da ara
    kırmızıya dönmemeli."""
    seen: list[httpx.Request] = []
    handler = _api(
        seen,
        fixtures={
            "soccer_epl": [_fixture("soccer_epl", _kickoff(16))],
            "soccer_turkey_super_league": [],
        },
    )

    code = _run(monkeypatch, tmp_path, handler)

    out = capsys.readouterr().out
    assert code == 0
    assert EMPTY_ROUND_LINE not in out
    assert [r for r in caplog.records if r.levelname == "ERROR"] == []
    assert len(_events_calls(seen)) == 2, "bekçi her ligi sormalıydı"


def test_a_round_that_wrote_rows_never_asks_for_fixtures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(c) Bir lig satır yazdıysa tur bugünkü gibi: kısmi boşluk KASITLI olarak işaretlenmez."""
    seen: list[httpx.Request] = []
    odds = {
        "soccer_epl": httpx.Response(
            200,
            json=[event("evt1", _kickoff(2), sport_key="soccer_epl")],
            headers=quota_headers(400),
        )
    }
    handler = _api(
        seen,
        odds=odds,
        fixtures={
            "soccer_turkey_super_league": [_fixture("soccer_turkey_super_league", _kickoff(1))]
        },
    )

    code = _run(monkeypatch, tmp_path, handler)

    assert code == 0
    assert _events_calls(seen) == []
    assert EMPTY_ROUND_LINE not in capsys.readouterr().out


def test_a_failing_fixture_check_warns_and_does_not_turn_the_round_red(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """(d) Bekçinin kendi ağ arızası toplayıcıyı kırmızıya çevirmez — ama logda adıyla durur."""
    seen: list[httpx.Request] = []
    handler = _api(seen, events_status=503)

    code = _run(monkeypatch, tmp_path, handler)

    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert code == 0
    assert EMPTY_ROUND_LINE not in capsys.readouterr().out
    assert any("fikstür kontrolü yapılamadı" in m and "eng.1" in m for m in warnings), (
        f"bekçinin arızası sessiz geçti: {warnings}"
    )
    assert all("TEST-KEY" not in m and "apiKey" not in m for m in warnings), "uyarı URL taşıyor"


def test_a_quota_stop_is_unchanged_and_asks_for_no_fixtures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(e) Kredi bitişinde tur zaten kırmızı; bekçi kodu ezmez, çağrı da yapmaz."""
    seen: list[httpx.Request] = []
    odds = {"soccer_epl": httpx.Response(200, json=[], headers=quota_headers(3))}

    code = _run(monkeypatch, tmp_path, _api(seen, odds=odds))

    assert code == collect.EXIT_QUOTA_EXHAUSTED
    assert _events_calls(seen) == []
    assert EMPTY_ROUND_LINE not in capsys.readouterr().out


def test_a_failed_league_is_unchanged_and_asks_for_no_fixtures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(e) Düşen lig zaten exit 3; boşluğu o ligin arızası açıklıyor olabilir."""
    seen: list[httpx.Request] = []
    odds = {"soccer_epl": httpx.Response(500, json={"message": "boom"})}
    fixtures = {"soccer_turkey_super_league": [_fixture("soccer_turkey_super_league", _kickoff(1))]}

    code = _run(monkeypatch, tmp_path, _api(seen, odds=odds, fixtures=fixtures))

    assert code == collect.EXIT_LEAGUE_FAILED
    assert _events_calls(seen) == []
    assert EMPTY_ROUND_LINE not in capsys.readouterr().out


def test_the_fixture_check_uses_the_odds_horizon(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(f) İki çağrı AYNI ufku sormalı: farklı ufuk, arayı arıza (ya da tersini) gösterir."""
    seen: list[httpx.Request] = []

    _run(monkeypatch, tmp_path, _api(seen))
    capsys.readouterr()

    horizons = {
        (
            request.url.path.rsplit("/", 1)[1],
            parse_qs(request.url.query.decode())["commenceTimeTo"][0],
        )
        for request in seen
    }
    odds = {value for kind, value in horizons if kind == "odds"}
    events = {value for kind, value in horizons if kind == "events"}
    assert len(odds) == 1 and odds == events, f"ufuklar ayrışıyor: odds={odds} events={events}"


def test_a_seal_round_never_asks_for_fixtures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Mühür turu değişmez: penceresi 20 dakika, boşluğu bekçinin sorusu değil."""
    now = datetime.now(UTC)
    seen: list[httpx.Request] = []
    db = _db_due_for_seal(now)
    _patch_main(monkeypatch, tmp_path, db, _api(seen))

    code = collect.main(["seal"])

    capsys.readouterr()
    assert code == 0
    assert _events_calls(seen) == []
