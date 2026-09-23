"""TFF PFDK kararları: windows-1254 çözümü, ayrıştırıcı sözleşmesi ve kaynak kaydı.

Fixture'lar (`tests/fixtures/pfdk/`) — KIRPILMIŞ ve TAKMA ADLI:
- Kaynak: `https://www.tff.org/default.aspx?pageID=238` (karar listesi) ve
  `https://www.tff.org/default.aspx?pageID=246&ftxtID=51404` (22.09.2026, 9 sayılı
  toplantı); 2026-09-23'te `tff-pfdk` kaynağından Scrapling adaptörü üzerinden (varsayılan
  `FetcherTransport`, robots.txt canlı 404) kaydedildi.
- Kırpma (düzeltme turu 1): yalnız ayrıştırıcının okuduğu kısım kaldı — listede 40
  `table.mhsiTable` satırı, kararda `div.haberDetailsFont`. Site iskeleti, `__VIEWSTATE`,
  betikler ve analitik düştü. Kalan kısım ham windows-1254 metnin dilimidir (yeniden
  serileştirilmedi: `&Uuml;` gibi varlıklar ve ham ı/İ/Ş/Ğ baytları sayfadaki gibi); başa
  kaynak ve değişiklik yorumu, çevresine `<html><body>` eklendi.
- Takma ad: kararlardaki yedi kişinin ve imzadaki kurul başkanının adı "<AD> ÖRNEK"
  biçiminde takma adla değiştirildi (aynı kişi her yerde aynı takma ad). Kulüp adları, maçlar
  ve ceza metni sayfadaki gibi. Dönüştürücü:
  `.superpowers/sdd/2026-09-23-oturum9-dalga-a/t3-scratch/t3r1_crop.py`.

`contract` etiketli testler sayfada GERÇEKTEN olan alanları sabitler (bkz.
`collectors/pfdk.py` modül docstring'i).

Bilinen sınırlar: tek bir karar sayfası kayıtlı (yalnız Ziraat Türkiye Kupası hükümleri, dört
rol, yedi ceza türü). Lig maçı, seyircisiz oynama, hak mahrumiyeti gibi hükümler bu fixture'da
YOK; o hükümler "diger" türüne düşer ve sayılır (yutulmaz) ama sınıflandırılmaz.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from football_edge.collect import ROBOTS_DIR, SOURCES_PATH
from football_edge.collector import ContractViolation
from football_edge.collectors import pfdk
from football_edge.scrape import BROWSER_USER_AGENT, Fetched, Guard, ScrapeRound
from football_edge.sources import audit_offline, load_sources

FIXTURES = Path(__file__).parent / "fixtures" / "pfdk"
LISTING = (FIXTURES / "pfdk-liste-238.html").read_bytes()
DECISIONS = (FIXTURES / "pfdk-karar-246-51404.html").read_bytes()
SOURCE = next(entry for entry in load_sources(SOURCES_PATH) if entry.id == pfdk.SOURCE_ID)


def page() -> pfdk.DecisionPage:
    return pfdk.parse_decisions(pfdk.decode(DECISIONS))


# ── windows-1254 ──────────────────────────────────────────────────────────────


@pytest.mark.contract
@pytest.mark.parametrize("body", [LISTING, DECISIONS], ids=["liste", "karar"])
def test_the_body_is_windows_1254_not_utf8(body: bytes) -> None:
    with pytest.raises(UnicodeDecodeError):
        body.decode("utf-8")
    assert b"\xfd" in body  # ı ham windows-1254 baytı: başka bir çözüm onu bozar
    text = pfdk.decode(body)
    assert "sayılı toplantısında" in text
    assert "<meta charset" not in text.lower()


# ── Liste (pageID=238) ────────────────────────────────────────────────────────


@pytest.mark.contract
def test_the_listing_links_every_decision_with_title_and_publication_dates() -> None:
    rows = pfdk.parse_listing(pfdk.decode(LISTING))
    assert len(rows) == 40
    assert rows[0] == pfdk.Listing(
        ftxt_id=51404,
        path=pfdk.RECORDED_DECISION_PATH,
        title="PFDK Kararları - 22.09.2026",
        title_date=date(2026, 9, 22),
        published=date(2026, 9, 22),
    )
    assert len({row.ftxt_id for row in rows}) == 40
    # Başlık tarihi ≠ yayım tarihi olabilir (07.09 kararı 8.09'da yayımlandı): ikisi ayrı alan.
    late = next(row for row in rows if row.ftxt_id == 51286)
    assert (late.title_date, late.published) == (date(2026, 9, 7), date(2026, 9, 8))


def test_a_listing_without_rows_is_loud() -> None:
    with pytest.raises(ContractViolation, match="satır yok"):
        pfdk.parse_listing("<html><body></body></html>")


# ── Karar sayfası (pageID=246) ────────────────────────────────────────────────


@pytest.mark.contract
def test_the_decision_page_carries_meeting_date_and_number() -> None:
    parsed = page()
    assert (parsed.meeting_date, parsed.meeting_no) == (date(2026, 9, 22), 9)
    assert len(parsed.decisions) == 14
    assert [d.item for d in parsed.decisions] == [1, 2, 3, 4, 5, 6, 7, 7, 8, 8, 8, 9, 9, 10]


@pytest.mark.contract
def test_every_decision_names_a_club_a_subject_a_match_and_a_classified_sanction() -> None:
    parsed = page()
    assert {d.role for d in parsed.decisions} == {"kulüp", "görevlisi", "sporcusu", "antrenörü"}
    for decision in parsed.decisions:
        assert decision.club
        assert (decision.role == "kulüp") == (decision.person is None)
        assert decision.match_date in {date(2026, 9, 15), date(2026, 9, 16)}
        assert decision.competition == "Ziraat Türkiye Kupası"
        assert decision.match and decision.club.split()[0] in decision.match
        assert decision.sanctions
        assert all(s.kind != "diger" for s in decision.sanctions), decision


@pytest.mark.contract
def test_sanction_kinds_and_durations_are_read_from_the_page() -> None:
    by_person = {d.person: d for d in page().decisions if d.person}
    player = by_person["DOĞAN ÖRNEK"]
    assert (player.club, player.role) == ("KAHTA 02 SPOR", "sporcusu")
    assert [(s.kind, s.value) for s in player.sanctions] == [("men", "1")]
    coach = by_person["ERDEM ÖRNEK"]
    assert (coach.club, coach.role, coach.item) == (
        "YENİ MERSİN İDMANYURDU FUTBOL A.Ş.",
        "antrenörü",
        9,
    )
    assert [(s.kind, s.value) for s in coach.sanctions] == [
        ("soyunma_odasi_yasagi", "1"),
        ("para", "10000"),
    ]
    official = by_person["TUĞRUL ÖRNEK"]
    assert [(s.kind, s.value) for s in official.sanctions] == [("soyunma_odasi_yasagi", "3")]


@pytest.mark.contract
def test_club_sanctions_and_continuations_inherit_the_match() -> None:
    decisions = page().decisions
    first = decisions[0]
    assert (first.club, first.match, first.match_date) == (
        "ALTAY",
        "ALTAY-SÖKE 1970 SPOR KULÜBÜ",
        date(2026, 9, 15),
    )
    assert [(s.kind, s.value) for s in first.sanctions] == [("para", "35000")]
    forfeit = decisions[2]
    assert [(s.kind, s.value) for s in forfeit.sanctions] == [
        ("hukmen_maglubiyet", "3-0"),
        ("ihrac", ""),
    ]
    continuation = decisions[7]  # "Aynı müsabakada" — maç metni paragrafta yok
    assert (continuation.person, continuation.match) == ("ŞAHİN ÖRNEK", "BAYBURTSPOR-BORÇKA SPOR")
    acquitted = [d for d in decisions if d.item == 8]
    assert [s.kind for d in acquitted for s in d.sanctions] == ["ceza_yok"] * 3


@pytest.mark.parametrize("fixture", [LISTING, DECISIONS], ids=["liste", "karar"])
def test_the_fixtures_are_cropped_to_the_parsed_part(fixture: bytes) -> None:
    assert b"__VIEWSTATE" not in fixture
    assert b"<script" not in fixture.lower()
    assert fixture.startswith(b"<!-- Kaynak: https://www.tff.org/default.aspx?pageID=")


def test_every_person_in_the_fixture_is_a_pseudonym() -> None:
    """Gerçek adlar depoya girmez: her kişi ve imza "… ÖRNEK" takma adını taşır."""
    persons = {d.person for d in page().decisions if d.person}
    assert len(persons) == 7
    assert all(person.endswith(" ÖRNEK") for person in persons), persons
    assert "Av. Yağız ÖRNEK" in pfdk.decode(DECISIONS)


@pytest.mark.parametrize(
    "paragraph",
    ["<p><strong>11-</strong> yalnız numara</p>", "<p>Aynı müsabakada özne yok</p>"],
    ids=["numara-tek-strong", "devam-strong-yok"],
)
def test_a_decision_paragraph_without_a_club_is_a_contract_violation(paragraph: str) -> None:
    text = pfdk.decode(DECISIONS).replace(
        "<p>Karar verilmiştir.</p>", f"{paragraph}<p>Karar verilmiştir.</p>"
    )
    with pytest.raises(ContractViolation, match="kulüp yok"):
        pfdk.parse_decisions(text)


def test_an_unrecognised_paragraph_is_loud_not_skipped() -> None:
    text = pfdk.decode(DECISIONS).replace(
        "<p>Karar verilmiştir.</p>", "<p>Yeni bir paragraf türü.</p><p>Karar verilmiştir.</p>"
    )
    with pytest.raises(ContractViolation, match="tanınmayan paragraf"):
        pfdk.parse_decisions(text)


def test_a_missing_decision_body_is_loud() -> None:
    text = pfdk.decode(DECISIONS).replace("haberDetailsFont", "baskaSinif")
    with pytest.raises(ContractViolation, match="haberDetailsFont"):
        pfdk.parse_decisions(text)


def test_an_unknown_sanction_is_counted_as_other_not_dropped() -> None:
    text = pfdk.decode(DECISIONS).replace("İHTAR CEZASI", "SEYİRCİSİZ OYNAMA CEZASI")
    kinds = [s.kind for d in pfdk.parse_decisions(text).decisions for s in d.sanctions]
    assert kinds.count("diger") == 1


# ── Kaynak kaydı ve adaptör üzerinden okuma ──────────────────────────────────


def test_the_source_is_registered_disabled_with_exactly_the_recorded_paths() -> None:
    assert SOURCE.enabled is False
    assert SOURCE.access_basis == "robots"
    assert SOURCE.declared_paths == (pfdk.LIST_PATH, pfdk.RECORDED_DECISION_PATH)


def test_the_declared_paths_pass_the_offline_policy_audit_when_enabled() -> None:
    """`enabled: false` kaynakları kapının `kaynak-politikası` adımı denetlemez; burada aynı
    denetim bu kayıt açılmış gibi koşar (anlık görüntü var, yollar robots'a uygun)."""
    audited = dataclasses.replace(SOURCE, enabled=True)
    assert audit_offline((audited,), ROBOTS_DIR, SOURCE.robots_verified_at) == ()


class FixtureTransport:
    def __init__(self, content_type: str) -> None:
        self.content_type = content_type
        self.calls: list[str] = []

    @property
    def user_agent(self) -> str:
        return BROWSER_USER_AGENT

    def get(self, url: str, guard: Guard) -> Fetched:
        guard(url, self.user_agent)
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return Fetched(url=url, status=404, headers={}, body=b"")
        return Fetched(
            url=url, status=200, headers={"content-type": self.content_type}, body=DECISIONS
        )


class InstantClock:
    def monotonic(self) -> float:
        return 0.0

    def sleep(self, seconds: float) -> None:
        del seconds

    def now(self) -> datetime:
        return datetime(2026, 9, 23, tzinfo=UTC)


def test_fetch_html_goes_through_the_adapter_and_decodes_windows_1254() -> None:
    transport = FixtureTransport("text/html; charset=windows-1254")
    scrape_round = ScrapeRound(clock=InstantClock(), robots_transport=transport)
    text = pfdk.fetch_html(scrape_round, pfdk.RECORDED_DECISION_PATH, transport)
    assert b"\xd0" in DECISIONS
    assert "DOĞAN ÖRNEK" in text  # Ğ ham windows-1254 baytı (0xD0); Ü/Ö/Ç ise &…; varlık
    assert transport.calls == [
        f"{SOURCE.base_url}/robots.txt",
        f"{SOURCE.base_url}{pfdk.RECORDED_DECISION_PATH}",
    ]


def test_fetch_html_refuses_a_charset_it_was_not_promised() -> None:
    transport = FixtureTransport("text/html; charset=utf-8")
    scrape_round = ScrapeRound(clock=InstantClock(), robots_transport=transport)
    with pytest.raises(ContractViolation, match="content-type"):
        pfdk.fetch_html(scrape_round, pfdk.RECORDED_DECISION_PATH, transport)
