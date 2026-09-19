"""TFF hakem ataması toplayıcısı testleri.

FIXTURE gerçek pageID=600 yanıtından (2026-09-19, `Tüm Liglerin Fikstürleri`)
yakalanmıştır — bkz. `task-6-report.md`. Brief pageID=433'ü ("Haftanın Hakem, Gözlemci
ve Temsilcileri") işaret ediyordu; ÖLÇÜLDÜ ki o sayfa varsayılan GET'te BOŞ bir arama
formu döner (Organizasyon → Grup → Hafta kademeli seçim + "Ara" düğmesi, hepsi
postback/AJAX) — DataList1 konteyneri sıfır satır taşır. Gerçek veri pageID=600'de:
`<div class="row haftaninMaclariMaclar">` ile tekrarlanan, GET'le doğrudan erişilebilir
bir blok, 7 lig, 63 maç (bugünkü anlık görüntüde).

FIXTURE_433 (`hakem-433.html`) bu ölçümün KANITIDIR — kendisi hiçbir pozitif testte
kullanılmaz, yalnız `test_referee_search_page_433_yields_no_rows`de PİNLENİR: brief'in
işaret ettiği sayfanın gerçekten sıfır satır ürettiğini ve `parse_referees`in o sayfada
UYDURMA satır ÜRETMEDİĞİNİ birlikte kanıtlar. Fixture rotarsa ya da silinirse bu test
kırmızı verir; aksi hâlde dosyanın varlığı yalnız bu docstring'e ve rapora güvenirdi.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.tff import collect_tff, parse_referees
from football_edge.naming import normalise_team
from tests.fake_obs_db import FakeObservationDb
from tests.fake_sources import write_robots

FIXTURE = Path("tests/fixtures/tff/haftanin-maclari-600.html")
FIXTURE_433 = Path("tests/fixtures/tff/hakem-433.html")
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def _drop_all_but_first_n_head_referees(html: str, *, keep: int) -> str:
    """`(H) ` önekini ilk `keep` tanesi HARİÇ kaldırır.

    Görevli hücresi hâlâ DOLU (Y/D/diğer roller duruyor), yalnız baş-hakem ETİKETİ
    kayboluyor — review Important #1'in ölçtüğü arıza sınıfının kaynakta üretimi: bir
    üst akış değişikliği hücreleri BOŞALTMAZ, yalnız etiketi taşıyan alt yapıyı
    değiştirir. Bu, hücrenin TAMAMEN boş olduğu meşru "TFF henüz atamamış" durumundan
    (bkz. `_officials_cell_is_empty`) kasıtlı olarak FARKLIDIR.
    """
    pattern = re.compile(r"\(H\) ")
    seen = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal seen
        seen += 1
        return match.group(0) if seen <= keep else ""

    return pattern.sub(_replace, html)


@pytest.mark.contract
def test_parses_this_weeks_fixtures() -> None:
    parsed = parse_referees(fixture_html(), observed_at=NOW)
    assert len(parsed) >= 5, f"haftalık program en az 5 maç taşımalı; {len(parsed)} bulundu"


@pytest.mark.contract
def test_turkish_characters_survive() -> None:
    """windows-1254 yanlış çözülürse 'Ü' ve 'ı' bozulur ve HİÇBİR eşleşme tutmaz."""
    parsed = parse_referees(fixture_html(), observed_at=NOW)
    joined = " ".join(
        f"{entry.payload['home_team']} {entry.payload['away_team']} {entry.payload['referee']}"
        for entry in parsed
    )
    assert "�" not in joined, "değiştirme karakteri var — kodlama yanlış çözüldü"
    assert any(letter in joined for letter in "çğıöşüÇĞİÖŞÜ"), "hiç Türkçe karakter yok"


@pytest.mark.contract
def test_every_row_has_a_referee() -> None:
    parsed = parse_referees(fixture_html(), observed_at=NOW)
    assert all(entry.payload["referee"].strip() for entry in parsed)


@pytest.mark.contract
def test_league_is_scoped_to_its_own_block_not_leaked_globally() -> None:
    """Ölçülen gerçek maç: KASIMPAŞA A.Ş. – TÜMOSAN KONYASPOR, blok='Trendyol Süper Lig
    Adnan Süvari Sezonu'. Lig adı ve maç satırları sayfada 7 AYRI konteynerde yaşıyor;
    eşleme konteyner-taramalı değil GLOBAL yapılsaydı (ör. son görülen `_lblMacOrgAdi`
    span'ini tüm sayfaya uygulamak) bu maç yanlış lige (ör. son blok 'Nesine 3. Lig')
    etiketlenebilirdi — sessiz yanlış veri, boş sonuçtan kötü.
    """
    parsed = parse_referees(fixture_html(), observed_at=NOW)
    match = next(
        entry
        for entry in parsed
        if entry.payload["home_team"] == "KASIMPAŞA A.Ş."
        and entry.payload["away_team"] == "TÜMOSAN KONYASPOR"
    )
    assert match.payload["league"] == "Trendyol Süper Lig Adnan Süvari Sezonu"
    assert match.payload["referee"] == "DAVUT DAKUL ÇELİK"


@pytest.mark.contract
def test_match_missing_a_head_referee_is_skipped_not_crashed() -> None:
    """Ölçüldü (2026-09-19): 63 maç satırından TAM 1'i hiç görevli taşımıyor (TFF henüz
    atamamış — gerçek bir durum, ayrıştırıcı arızası değil, footystats'taki "her satır
    ayrıştırılmalı" kuralının burada UYGULANMAMASININ nedeni budur). O satır sessizce
    atlanır; sayı burada SABİTLENİR ki bir gerileme (ör. atlama koşulu tersine döner ve
    boş `referee` yazılmaya başlar) sessizce geçmesin.
    """
    parsed = parse_referees(fixture_html(), observed_at=NOW)
    assert len(parsed) == 62


def test_partial_referee_loss_raises_rather_than_undercounting() -> None:
    """review Important #1 (ölçülerek kanıtlandı): 62 satırdan 56'sı `(H)` etiketini
    kaybederse ESKİ davranış SESSİZCE 5 gözlem yazıp `assert_schema(minimum_rows=5)`i
    geçiyordu — 62 yerine 5 "başarı" diye raporlanıyordu, hiçbir uyarı olmadan.

    Bu satırların görevli hücresi hâlâ DOLU (yalnız `(H)` etiketi yok) — bu yüzden
    `_officials_cell_is_empty` onları "meşru boşluk" SAYMAZ, `unassigned`e eklenmezler,
    ve `len(parsed) + unassigned < total_rows` tutar: `ContractViolation` fırlamalı.
    """
    degraded = _drop_all_but_first_n_head_referees(fixture_html(), keep=6)
    with pytest.raises(ContractViolation, match="görevlisiz"):
        parse_referees(degraded, observed_at=NOW)


@pytest.mark.contract
def test_referee_search_page_433_yields_no_rows() -> None:
    """`hakem-433.html`i PİNLER (bkz. modül docstring'i): brief'in işaret ettiği sayfa
    gerçekten sıfır satır üretir VE `parse_referees` o sayfadan UYDURMA satır türetmez —
    ikisi birden, fixture'ın kendisi çürüse/silinse kırmızı verecek TEK testte.
    """
    html = FIXTURE_433.read_text(encoding="utf-8")
    with pytest.raises(ContractViolation):
        parse_referees(html, observed_at=NOW)


def test_empty_page_raises_rather_than_returning_empty() -> None:
    with pytest.raises(ContractViolation):
        parse_referees("<html><body></body></html>", observed_at=NOW)


def test_team_normalisation_is_case_and_space_insensitive() -> None:
    """Eşleşme anahtarı normalize edilir; 'Galatasaray A.Ş.' ile 'GALATASARAY' aynı olmalı."""
    assert normalise_team("  Galatasaray A.Ş. ") == normalise_team("GALATASARAY AŞ")


def _write_sources_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(
        """
sources:
  - id: tff
    base_url: https://tff.test
    user_agent: football-edge-test/0.1
    crawl_delay_seconds: 0.0
    robots_verified_at: 2026-09-19
    declared_paths: ['/Default.aspx?pageID=600']
    enabled: true
    access_basis: robots
    terms_url: ''
    note: ''
""",
        encoding="utf-8",
    )
    return path


def test_collect_tff_writes_observations_and_commits(tmp_path: Path) -> None:
    sources_path = _write_sources_yaml(tmp_path)
    write_robots(tmp_path, "tff", "")  # ölçülen gerçek durum: robots.txt 404 → boş anlık görüntü

    def handler(request: httpx.Request) -> httpx.Response:
        assert "pageID=600" in str(request.url)
        return httpx.Response(
            200,
            content=fixture_html().encode("windows-1254"),
            headers={"content-type": "text/html; charset=windows-1254"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    db = FakeObservationDb()

    written = collect_tff(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert written == 62
    assert len(db.rows) == 62


def test_collect_tff_second_round_is_idempotent(tmp_path: Path) -> None:
    """Aynı hafta iki kez toplanırsa ikinci tur 0 YENİ gözlem yazmalı (`ON CONFLICT DO
    NOTHING` — `write_observations` zaten bunu garanti ediyor; burada TFF'in bu
    garantiyi bypass ETMEDİĞİ doğrulanıyor, ör. `observed_at`i hash'e sızdırarak).
    """
    sources_path = _write_sources_yaml(tmp_path)
    write_robots(tmp_path, "tff", "")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=fixture_html().encode("windows-1254"),
            headers={"content-type": "text/html; charset=windows-1254"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    db = FakeObservationDb()

    first = collect_tff(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )
    second = collect_tff(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert first == 62
    assert second == 0
