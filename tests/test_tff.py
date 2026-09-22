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

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

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


_OFFICIALS_CELL_CLASS = "haftaninMaclariMaclarHakemler"


def _week_with_no_assignments(html: str) -> str:
    """Her görevli hücresini TAMAMEN boşaltır.

    2026-09-22'de canlı ölçülen durum budur: `pageID=600` yine 7 lig bloğu ve 63 maç
    satırı taşıyor, ama 63 hücrenin HEPSİ `<a>`sız, metinsiz ve alt etiketsiz — TFF o
    haftanın hakemlerini henüz açıklamamış. Fixture'daki tek atanmamış satırın hücresi de
    tam olarak bu şekilde (ölçüldü). Canlı sayfa depoya girmez (Ruling 4); durum mevcut
    fixture'dan türetilir.
    """
    soup = BeautifulSoup(html, "html.parser")
    for cell in soup.find_all("div", class_=_OFFICIALS_CELL_CLASS):
        cell.clear()
    return str(soup)


def _officials_as_plain_text(html: str, *, keep_links: int) -> str:
    """İlk `keep_links` dolu hücre HARİÇ görevli bağlantılarını düz metne çevirir.

    `<a>` açılır, isim METİN olarak hücrede kalır: bir üst akış değişikliği (ör. TFF
    hakem profil bağlantılarını kaldırır) hücreyi BOŞALTMAZ. Bu hücreler "TFF henüz
    atamamış" sayılırsa kayıp sessizce "görevlisiz" diye geçer — boş hücreden FARKLIDIR.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen = 0
    for cell in soup.find_all("div", class_=_OFFICIALS_CELL_CLASS):
        links = cell.find_all("a")
        if not links:
            continue
        seen += 1
        if seen <= keep_links:
            continue
        for link in links:
            link.unwrap()
    return str(soup)


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


def test_week_with_no_assignments_yet_is_empty_not_a_shape_change(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """İlk canlı `collect-daily` turu (2026-09-22, run 35710579845) burada kırmızıydı:
    sayfa şekli SAĞLAMDI (7 blok, 63 satır, 63 boş hücre) ama "hiç hakem ataması
    tanınmadı — sayfa şekli değişti" fırlıyordu. Hakemler her hafta maçlardan birkaç gün
    önce açıklanır; bu durum haftada birkaç gün GERÇEKTİR, arıza değildir.

    Boş sonuç sessiz de değildir: kaç maçın görevlisiz olduğu adıyla loglanır.
    """
    caplog.set_level(logging.INFO, logger="football_edge.collectors.tff")

    parsed = parse_referees(_week_with_no_assignments(fixture_html()), observed_at=NOW)

    assert parsed == ()
    assert "63 maç için hakem ataması henüz yayınlanmamış" in caplog.text


def test_officials_named_without_links_are_a_loss_not_unassigned() -> None:
    """Görevli hücresi DOLU ama `<a>` taşımıyorsa o maç "TFF henüz atamamış" DEĞİLDİR.

    Eski `_officials_cell_is_empty` yalnız `<a>` yokluğuna bakıyordu: 62 dolu satırdan
    56'sı bağlantısız isme dönünce 6 gözlem yazılıp 57 satır "görevlisiz" sayılıyordu —
    56 satırlık kayıp hatasız "başarı" olarak geçiyordu.
    """
    degraded = _officials_as_plain_text(fixture_html(), keep_links=6)
    with pytest.raises(ContractViolation, match="görevlisiz"):
        parse_referees(degraded, observed_at=NOW)


def test_all_officials_named_without_links_still_raises() -> None:
    """Atanmamış haftanın boş dönmesi (yukarıdaki test) bir deliğe dönüşmemeli: TFF bütün
    görevlileri bağlantısız metin olarak basmaya başlarsa her gün 0 yazıp yeşil kalırdık.
    Hücre metin taşıdığı sürece o satır meşru boşluk sayılmaz.
    """
    degraded = _officials_as_plain_text(fixture_html(), keep_links=0)
    with pytest.raises(ContractViolation, match="görevlisiz"):
        parse_referees(degraded, observed_at=NOW)


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


def test_collect_tff_week_with_no_assignments_writes_nothing_and_succeeds(
    tmp_path: Path,
) -> None:
    """`assert_schema(minimum_rows=5)` atanmamış haftayı YENİDEN kırmızıya çevirmemeli:
    `parse_referees` boş sonucu yalnız her satır meşru olarak görevlisizken döner.
    """
    sources_path = _write_sources_yaml(tmp_path)
    write_robots(tmp_path, "tff", "")
    page = _week_with_no_assignments(fixture_html())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=page.encode("windows-1254"),
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

    assert written == 0
    assert db.rows == []
