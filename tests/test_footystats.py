from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.footystats import collect_footystats, parse_xg_table
from football_edge.leagues import League
from tests.fake_obs_db import FakeObservationDb
from tests.fake_sources import write_robots

FIXTURE = Path("tests/fixtures/footystats/turkey-super-lig-xg.html")
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.mark.contract
def test_parses_every_team_in_the_league() -> None:
    parsed = parse_xg_table(fixture_html(), league_id="tur.1", observed_at=NOW)
    assert len(parsed) >= 18, f"Süper Lig 18+ takım; {len(parsed)} ayrıştırıldı"


@pytest.mark.contract
def test_payload_carries_the_required_fields_in_plausible_ranges() -> None:
    parsed = parse_xg_table(fixture_html(), league_id="tur.1", observed_at=NOW)
    for entry in parsed:
        assert entry.payload["team_name"]
        assert entry.payload["footystats_id"] > 0
        assert entry.payload["matches_played"] >= 0
        # MAÇ BAŞINA xG (review #1): FootyStats bu tabloda sezon toplamı değil, maç
        # başına ortalama veriyor — ölçüldü, Galatasaray MP=5 GF=2.60: 5 maçta 2.6 gol
        # OLAMAZ, `xG vs Actual` = GF - xG = +0.10 da bunu doğruluyor. 0-5 makul üst
        # sınır; aralık iddiası ayrıştırıcının yanlış SÜTUNU (ör. bir sezon-toplamı
        # sütunu) okuduğunu yakalar.
        assert 0.0 <= entry.payload["xg_per_match"] <= 5.0
        assert 0.0 <= entry.payload["xga_per_match"] <= 5.0


@pytest.mark.contract
def test_entity_key_is_league_scoped_and_stable() -> None:
    parsed = parse_xg_table(fixture_html(), league_id="tur.1", observed_at=NOW)
    keys = tuple(entry.entity_key for entry in parsed)
    assert len(set(keys)) == len(keys), "yinelenen entity_key — join sessizce çoğaltır"
    assert all(key.startswith("tur.1:") for key in keys)


def test_missing_table_raises_rather_than_returning_empty() -> None:
    """Kırılan ayrıştırıcı BOŞ LİSTE döndürmemeli: boş liste sessizce başarı gibi görünür."""
    with pytest.raises(ContractViolation, match="xg-all"):
        parse_xg_table("<html><body>hiçbir şey</body></html>", league_id="tur.1", observed_at=NOW)


def test_renamed_column_raises() -> None:
    """Sütun adı değişirse indeksle okumak YANLIŞ SAYIYI sessizce alır. Ad kontrol edilir."""
    broken = (
        "<table class='xg-all'><thead><tr><th>#</th><th>Team</th><th>MP</th>"
        "<th>ExpG</th><th>ExpGA</th></tr></thead><tbody></tbody></table>"
    )
    with pytest.raises(ContractViolation, match="xG"):
        parse_xg_table(broken, league_id="tur.1", observed_at=NOW)


def test_a_row_that_silently_fails_to_parse_raises_rather_than_undercounting() -> None:
    """review #5: bir satır (kısa satır / eşleşmeyen href) sessizce atlanırsa
    `assert_schema(minimum_rows=10)` bunu YAKALAMAZ — ligin yarısı sessizce kaybolup
    yine de eşiği geçebilir. İkinci satırın href'i regex'e uymuyor (büyük harf, sayısal
    kimlik yok) — takım hücresi VAR ama takım kimliği ÇIKARILAMIYOR."""
    broken = (
        "<table class='xg-all'><thead><tr><th>#</th><th>Team</th><th>MP</th>"
        "<th>xG</th><th>xGA</th></tr></thead><tbody>"
        "<tr><td>1</td><td><a href='/clubs/team-1'>Team One</a></td><td>5</td>"
        "<td>1.5</td><td>1.0</td></tr>"
        "<tr><td>2</td><td><a href='/clubs/TeamTwo'>Team Two</a></td><td>5</td>"
        "<td>1.2</td><td>0.9</td></tr>"
        "</tbody></table>"
    )
    with pytest.raises(ContractViolation, match="tur.1"):
        parse_xg_table(broken, league_id="tur.1", observed_at=NOW)


def _write_sources_yaml(tmp_path: Path, *, enabled: bool = True, present: bool = True) -> Path:
    path = tmp_path / "sources.yaml"
    if not present:
        path.write_text("sources: []\n", encoding="utf-8")
        return path
    path.write_text(
        f"""
sources:
  - id: footystats
    base_url: https://footystats.test
    user_agent: football-edge-test/0.1
    crawl_delay_seconds: 0.0
    robots_verified_at: 2026-09-19
    declared_paths: ['/good/xg', '/bad/xg']
    enabled: {"true" if enabled else "false"}
    access_basis: robots
    terms_url: ''
    note: ''
""",
        encoding="utf-8",
    )
    return path


def _league(league_id: str, path: str) -> League:
    return League(
        id=league_id,
        odds_api_key="x",
        name=league_id,
        country="X",
        lang="en",
        gl="GB",
        active=True,
        footystats_path=path,
    )


def test_collect_raises_a_named_error_when_the_source_is_disabled(tmp_path: Path) -> None:
    """review #2: `enabled: false` bir kapatma anahtarıdır, sessizce yok sayılmamalı.

    `write_robots` BİLİNÇLİ çağrılıyor (gerçek dünyada kapalı bir kaynağın robots
    anlık görüntüsü diskte hâlâ durabilir, yalnız kullanılmaz): kaynak seçimi robots
    okumadan ÖNCE gerçekleşmeli, bu yüzden dosya var olsa bile hiç okunmamalı — kaynak
    seçimi kırılırsa (mutasyon: enabled filtresi kaldırılırsa) arıza 'robots dosyası
    yok' gibi İLGİSİZ bir hatayla değil, doğrudan burada yakalanmalı.
    """
    sources_path = _write_sources_yaml(tmp_path, enabled=False)
    write_robots(tmp_path, "footystats", "")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")))
    db = FakeObservationDb()

    with pytest.raises(RuntimeError, match="enabled=false"):
        collect_footystats(
            db,  # type: ignore[arg-type]
            client,
            (_league("tur.1", "/good/xg"),),
            sources_path=sources_path,
            robots_dir=tmp_path,
            now=NOW,
        )


def test_collect_raises_a_named_error_when_the_source_is_missing(tmp_path: Path) -> None:
    """review #2: kayıt hiç yoksa da aynı adlandırılmış hata — çıplak StopIteration değil."""
    sources_path = _write_sources_yaml(tmp_path, present=False)
    write_robots(tmp_path, "footystats", "")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")))
    db = FakeObservationDb()

    with pytest.raises(RuntimeError, match="kaynak kaydı yok"):
        collect_footystats(
            db,  # type: ignore[arg-type]
            client,
            (_league("tur.1", "/good/xg"),),
            sources_path=sources_path,
            robots_dir=tmp_path,
            now=NOW,
        )


def test_collect_isolates_a_failing_league_but_still_reports_it(tmp_path: Path) -> None:
    """review #3: bir ligin arızası diğerini düşürmemeli, AMA sessizce de geçilmemeli.

    Eskiden `collect_footystats` yalnız `int` dönüyordu: altı ligin HEPSİ kırılsa bile
    çıktı "footystats: 0 yeni gözlem" olur, bu da ikinci turun idempotent 0'ından hiçbir
    çıktı farkıyla ayırt edilemezdi.
    """
    sources_path = _write_sources_yaml(tmp_path)
    write_robots(tmp_path, "footystats", "")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/bad/" in str(request.url):
            return httpx.Response(500, text="boom")
        return httpx.Response(200, text=fixture_html(), headers={"content-type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    db = FakeObservationDb()

    result = collect_footystats(
        db,  # type: ignore[arg-type]
        client,
        (_league("bad.1", "/bad/xg"), _league("good.1", "/good/xg")),
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result.written > 0, "sağlam lig yine de yazılmalıydı"
    assert result.failed_leagues == ("bad.1",), f"arızalı lig raporlanmadı: {result.failed_leagues}"
    assert db.rollbacks == 1, "arızalı ligin transaction'ı geri alınmalıydı"


def test_collect_does_not_count_a_league_whose_commit_fails(tmp_path: Path) -> None:
    """I-1 (Faz 1 SON inceleme, 2026-09-19) — Minor #4/G1 ile AYNI sınıf arıza, bu REFERANS
    toplayıcıda: "not failed" ile "durably written" aynı şey değildir. `commit()` düşerse
    satır kalıcı DEĞİLDİR; `written`i önceden artırmak hiç kalıcı olmamış veri için "N yeni
    gözlem" basmak demektir. R48 bu düzeltmeyi venues.py/news.py/results.py'a taşıdı ama
    Task 5 (bu dosya) R48'DEN ÖNCEYDİ ve geri süpürülmedi — `FakeObservationDb.commit_fails`
    kardeşleriyle AYNI desen, tam bunun için var.
    """
    sources_path = _write_sources_yaml(tmp_path)
    write_robots(tmp_path, "footystats", "")
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, text=fixture_html(), headers={"content-type": "text/html"}
            )
        )
    )
    db = FakeObservationDb(commit_fails=lambda _db: True)

    result = collect_footystats(
        db,  # type: ignore[arg-type]
        client,
        (_league("good.1", "/good/xg"),),
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result.written == 0, f"commit düştü ama written sayıldı: {result}"
    assert result.failed_leagues == ("good.1",)
    assert db.rollbacks == 1
