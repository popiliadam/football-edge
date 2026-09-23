"""TFF PFDK (Profesyonel Futbol Disiplin Kurulu) kararları — ayrıştırıcı ve fixture okuması.

Kaynak `tff-pfdk` (`config/sources.yaml`, `enabled: false`). YALNIZ Scrapling adaptörü
(`football_edge.scrape`) üzerinden istenir; bu modül veritabanına YAZMAZ ve zamanlanmaz — yazma ve
zamanlama Plan 2'ye (oturum 9 Task 3 brief'i).

Ölçülen sayfa şekli (2026-09-23, adaptör üzerinden canlı kayıt; depodaki fixture'lar bu iki parçaya
kırpılmış ve kişi adları takma adlı — tests/test_pfdk.py docstring'i):

- `pageID=238` karar LİSTESİ: 40 satır, her biri `table.mhsiTable`; başlık bağlantısı
  (`span.yaziTre a`, `href='/default.aspx?pageID=246&ftxtID=<n>'`, metin "PFDK Kararları -
  GG.AA.YYYY") ve yayım tarihi (`span.griTxt`, gün ÖNDE SIFIRSIZ: "8.09.2026"). Başlık tarihi ile
  yayım tarihi her zaman aynı DEĞİL (07.09 kararı 8.09'da yayımlanmış). Sonraki sayfalar ASP.NET
  postback'i — POST, istenmez.
- `pageID=246&ftxtID=<n>` tek karar metni: `div.haberDetailsFont` içinde `<p>` başına bir hüküm.
  Giriş paragrafı toplantı tarihini ve sayısını taşır ("… 22.09.2026 tarih ve 9 sayılı
  toplantısında …"). Hüküm paragrafı ya `<strong>N-</strong>` ile başlar ya da "Aynı müsabakada"
  ile (bir önceki numaranın maçına ek hüküm). İlk `<strong>` kulüp; ardından "Kulübünün" /
  "Kulübü hakkında" / "’nin" (kulübün kendisi) ya da "[Kulübü] <rol> <strong>KİŞİ</strong>" gelir.
  Kalan `<strong>`lar ceza hükümleridir (büyük harf). Maç: "GG.AA.YYYY tarihinde oynanan
  EV-DEPLASMAN <Organizasyon> müsabakasında". Sonda "Karar verilmiştir.", imza ve not.
- Charset YALNIZ HTTP başlığında (`text/html; charset=windows-1254`), gövdede meta yok.

Sayfada olup ayrıştırılMAYAN: FDT madde numaraları ("FDT’nin 44/1-c maddesi"), gerekçe metni,
imza. Ev/deplasman ayrımı yapılmaz: maç dizesi olduğu gibi tutulur (takım adında `-` olabilir).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from bs4 import BeautifulSoup, NavigableString, Tag

from football_edge.collector import ContractViolation
from football_edge.scrape import REGISTRY_PATH, ScrapeRound, Transport
from football_edge.sources import load_sources

SOURCE_ID = "tff-pfdk"
ENCODING = "windows-1254"
LIST_PATH = "/default.aspx?pageID=238"
# Fixture'ı kaydedilen karar (22.09.2026, 9 sayılı toplantı). declared_paths yalnız bunu taşır (R7).
RECORDED_DECISION_PATH = "/default.aspx?pageID=246&ftxtID=51404"

_DECISION_HREF = re.compile(r"^/default\.aspx\?pageID=246&ftxtID=(\d+)$")
_DATE = r"(\d{1,2}\.\d{2}\.\d{4})"
_MEETING = re.compile(rf"{_DATE} tarih ve (\d+) sayılı toplantısında")
_ITEM = re.compile(r"^(\d+)-$")
_MATCH = re.compile(rf"{_DATE} tarihinde oynanan (.+?) müsabakasında")
_MATCH_AND_COMPETITION = re.compile(r"^(.*?[A-ZÇĞİÖŞÜ0-9.)])\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü].*)$")
_CONTINUATION = "Aynı müsabakada"
_CLUB_SUBJECT = re.compile(r"^\s*(?:Kulübünün|Kulübü hakkında|[’']n[ıiuü]n)\b")
_PERSON_ROLE = re.compile(r"^\s*(?:Kulübü\s+)?([a-zçğıöşü]+)\s*$")
_FOOTER = ("Karar verilmiştir.", "PFDK Başkanı", "(*) İşbu karar")

# (tür, desen) — sırayla, ilk eşleşen kazanır. Tutar/süre ilk yakalama grubundadır.
_SANCTIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("para", re.compile(r"([\d.]+)\.-TL PARA CEZASI")),
    ("men", re.compile(r"(\d+) RESMİ MÜSABAKADAN MEN CEZASI")),
    ("soyunma_odasi_yasagi", re.compile(r"(\d+) RESMİ MÜSABAKADA SOYUNMA ODASINA")),
    ("hukmen_maglubiyet", re.compile(r"\((\d+-\d+)\) HÜKMEN MAĞLUP")),
    ("ihrac", re.compile(r"()İHRAÇ EDİLMESİNE")),
    ("ihtar", re.compile(r"()İHTAR CEZASI")),
    ("ceza_yok", re.compile(r"()CEZA TAYİNİNE YER OLMADIĞINA")),
)


@dataclass(frozen=True)
class Listing:
    ftxt_id: int
    path: str
    title: str
    title_date: date
    published: date


@dataclass(frozen=True)
class Sanction:
    kind: str  # _SANCTIONS türlerinden biri ya da "diger" (sınıflanamadı — sayılır, yutulmaz)
    value: str  # TL tutarı (nokta ayraçsız), müsabaka sayısı, skor ya da ""
    raw: str


@dataclass(frozen=True)
class Decision:
    item: int
    club: str
    role: str  # "kulüp" ya da sayfadaki rol sözcüğü ("sporcusu", "görevlisi", "antrenörü", …)
    person: str | None
    match_date: date | None
    match: str | None
    competition: str | None
    sanctions: tuple[Sanction, ...]


@dataclass(frozen=True)
class DecisionPage:
    meeting_date: date
    meeting_no: int
    decisions: tuple[Decision, ...]


def decode(body: bytes) -> str:
    """TFF gövdesi windows-1254; tahmine bırakılırsa Türkçe adlar sessizce bozulur."""
    return body.decode(ENCODING, errors="strict")


def _day(text: str) -> date:
    return datetime.strptime(text.strip(), "%d.%m.%Y").date()


def _text(node: Tag | NavigableString) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def parse_listing(html_text: str) -> tuple[Listing, ...]:
    soup = BeautifulSoup(html_text, "html.parser")
    rows: tuple[Listing, ...] = ()
    for table in soup.find_all("table", class_="mhsiTable"):
        title = table.find("span", class_="yaziTre")
        published = table.find("span", class_="griTxt")
        link = title.find("a") if isinstance(title, Tag) else None
        if not isinstance(link, Tag) or not isinstance(published, Tag):
            raise ContractViolation(f"{SOURCE_ID}: liste satırında başlık ya da tarih yok")
        href = str(link.get("href", ""))
        found = _DECISION_HREF.match(href)
        title_date = re.search(_DATE, _text(link))
        if found is None or title_date is None:
            raise ContractViolation(f"{SOURCE_ID}: beklenmeyen liste satırı {href!r}")
        rows = (
            *rows,
            Listing(
                ftxt_id=int(found.group(1)),
                path=href,
                title=_text(link),
                title_date=_day(title_date.group(1)),
                published=_day(_text(published)),
            ),
        )
    if not rows:
        raise ContractViolation(f"{SOURCE_ID}: karar listesinde satır yok")
    return rows


def _sanctions(strongs: list[Tag]) -> tuple[Sanction, ...]:
    found: tuple[Sanction, ...] = ()
    for strong in strongs:
        raw = _text(strong).rstrip(",").strip()
        if not raw:
            continue
        kind, value = next(
            ((kind, hit.group(1)) for kind, pattern in _SANCTIONS if (hit := pattern.search(raw))),
            ("diger", ""),
        )
        found = (*found, Sanction(kind=kind, value=value.replace(".", ""), raw=raw))
    return found


def _subject(club: Tag) -> tuple[str, str | None, int]:
    """Kulübün ardından gelen metinden özneyi okur: (rol, kişi, tüketilen <strong> sayısı)."""
    following = club.next_sibling
    text = str(following) if isinstance(following, NavigableString) else ""
    if _CLUB_SUBJECT.match(text):
        return "kulüp", None, 0
    role = _PERSON_ROLE.match(text)
    person = following.next_sibling if following is not None else None
    if role is None or not isinstance(person, Tag) or person.name != "strong":
        raise ContractViolation(f"{SOURCE_ID}: özne okunamadı: {_text(club)!r} {text!r}")
    return role.group(1), _text(person), 1


def _match(text: str) -> tuple[date, str, str | None] | None:
    found = _MATCH.search(text)
    if found is None:
        return None
    split = _MATCH_AND_COMPETITION.match(found.group(2))
    if split is None:
        return _day(found.group(1)), found.group(2), None
    return _day(found.group(1)), split.group(1), split.group(2)


def _decision(paragraph: Tag, previous: Decision | None) -> Decision:
    strongs = [node for node in paragraph.find_all("strong") if isinstance(node, Tag)]
    number = _ITEM.match(_text(strongs[0])) if strongs else None
    if number is None and previous is None:
        raise ContractViolation(f"{SOURCE_ID}: numarasız ilk hüküm: {_text(paragraph)[:80]!r}")
    club_index = 1 if number is not None else 0
    if len(strongs) <= club_index:
        raise ContractViolation(f"{SOURCE_ID}: hükümde kulüp yok: {_text(paragraph)[:80]!r}")
    club_tag = strongs[club_index]
    role, person, consumed = _subject(club_tag)
    sanctions = _sanctions(strongs[strongs.index(club_tag) + 1 + consumed :])
    if not sanctions:
        raise ContractViolation(f"{SOURCE_ID}: hükümde ceza yok: {_text(paragraph)[:80]!r}")
    match = _match(_text(paragraph))
    if number is None and previous is not None:
        # "Aynı müsabakada": maç bir önceki hükmünkü, numara da onunki.
        return Decision(
            item=previous.item,
            club=_text(club_tag),
            role=role,
            person=person,
            match_date=match[0] if match else previous.match_date,
            match=match[1] if match else previous.match,
            competition=match[2] if match else previous.competition,
            sanctions=sanctions,
        )
    return Decision(
        item=int(number.group(1)) if number is not None else 0,
        club=_text(club_tag),
        role=role,
        person=person,
        match_date=match[0] if match else None,
        match=match[1] if match else None,
        competition=match[2] if match else None,
        sanctions=sanctions,
    )


def parse_decisions(html_text: str) -> DecisionPage:
    """Bir karar sayfasını hükümlere çevirir. Tanınmayan her paragraf GÜRÜLTÜLÜ hatadır:
    sessizce atlanan bir paragraf, kaybolmuş bir cezadır (Ruling 6)."""
    body = BeautifulSoup(html_text, "html.parser").find("div", class_="haberDetailsFont")
    if not isinstance(body, Tag):
        raise ContractViolation(f"{SOURCE_ID}: karar gövdesi (div.haberDetailsFont) yok")
    paragraphs = [p for p in body.find_all("p") if isinstance(p, Tag) and _text(p)]
    meeting = _MEETING.search(_text(paragraphs[0])) if paragraphs else None
    if meeting is None:
        raise ContractViolation(f"{SOURCE_ID}: toplantı tarihi/sayısı paragrafı yok")
    decisions: tuple[Decision, ...] = ()
    for paragraph in paragraphs[1:]:
        text = _text(paragraph)
        if any(text.startswith(marker) for marker in _FOOTER) or _is_signature(paragraph):
            continue
        strongs = paragraph.find_all("strong")
        is_item = bool(strongs) and _ITEM.match(_text(strongs[0])) is not None
        if not is_item and not text.startswith(_CONTINUATION):
            raise ContractViolation(f"{SOURCE_ID}: tanınmayan paragraf: {text[:80]!r}")
        decisions = (*decisions, _decision(paragraph, decisions[-1] if decisions else None))
    if not decisions:
        raise ContractViolation(f"{SOURCE_ID}: karar sayfasında hüküm yok")
    return DecisionPage(
        meeting_date=_day(meeting.group(1)),
        meeting_no=int(meeting.group(2)),
        decisions=decisions,
    )


def _is_signature(paragraph: Tag) -> bool:
    """İmza satırı ("Av. Ad SOYAD"): `<strong>`suz, hükümden sonra, "Karar verilmiştir."in
    ardından gelir. Yalnız o paragraf tipine izin verilir: kardeşlerde karar kapanışı aranır."""
    previous = paragraph.find_previous_sibling("p")
    return (
        not paragraph.find("strong")
        and isinstance(previous, Tag)
        and _text(previous) == "Karar verilmiştir."
    )


def fetch_html(scrape_round: ScrapeRound, path: str, transport: Transport | None = None) -> str:
    """`tff-pfdk` kaynağından bir beyanlı yolu adaptör üzerinden ister ve windows-1254 çözer.

    Charset yalnız başlıkta: başlık başka bir şey derse sözleşme bozulmuştur (tahmin yok)."""
    source = next(entry for entry in load_sources(REGISTRY_PATH) if entry.id == SOURCE_ID)
    fetched = scrape_round.session(source, transport).get(f"{source.base_url}{path}")
    content_type = fetched.header("content-type").lower()
    if "text/html" not in content_type or ENCODING not in content_type:
        raise ContractViolation(f"{SOURCE_ID}: beklenmeyen content-type {content_type!r} ({path})")
    return decode(fetched.body)
