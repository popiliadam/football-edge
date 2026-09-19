from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.robotparser import RobotFileParser

import yaml


class SourceBlocked(RuntimeError):
    """Kaynak politikası bu yolu kapatıyor. İstek ATILMAZ.

    Spec §3.2/1-2: robots.txt'i otomatik erişime kapalı kaynak taranmaz, erişim kontrolü
    aşılmaz. Bu istisna o kuralın KODDAKİ karşılığıdır; yakalanıp yutulursa kural yine
    prose'a döner.
    """


# access_basis: hangi mekanizma bu kaynağa erişimi haklı çıkarıyor. Spec §3.2 kendi
# içinde ayırıyor: madde 1 ROBOTS.TXT'İ TARAYICILAR için (bkz. ACCESS_BASIS_ROBOTS —
# varsayılan, mevcut davranış), madde 3 ise TOS'u ayrı bir sınama olarak ele alıyor
# (bkz. ACCESS_BASIS_API_TERMS). Bir API sunucusunun robots.txt'i o sunucuyu kazıyan
# TARAYICILARI hedefler, belgelenmiş bir API'nin istemcisini değil — ikisini karıştırmak
# R8'in bulduğu hatanın ta kendisiydi.
ACCESS_BASIS_ROBOTS = "robots"
ACCESS_BASIS_API_TERMS = "api_terms"
VALID_ACCESS_BASES = frozenset({ACCESS_BASIS_ROBOTS, ACCESS_BASIS_API_TERMS})


@dataclass(frozen=True)
class Source:
    id: str
    base_url: str
    user_agent: str
    crawl_delay_seconds: float
    robots_verified_at: date
    declared_paths: tuple[str, ...]
    enabled: bool
    note: str
    access_basis: str
    # access_basis=api_terms İÇİN ZORUNLU (bkz. audit_offline); robots-tabanlı kaynaklarda ''.
    # İstisna GEREKÇESİZ olamaz — boş kalırsa kapı kırmızı verir, dipnot olarak kaybolmaz.
    terms_url: str


REQUIRED_FIELDS = frozenset(
    {
        "id",
        "base_url",
        "user_agent",
        "crawl_delay_seconds",
        "robots_verified_at",
        "declared_paths",
        "enabled",
        "note",
        "access_basis",
        "terms_url",
    }
)


def _validate(entry: dict[str, Any], seen: frozenset[str]) -> None:
    keys = frozenset(entry)
    missing = REQUIRED_FIELDS - keys
    if missing:
        raise ValueError(f"kaynak kaydında eksik alan: {sorted(missing)} ({entry.get('id', '?')})")
    unknown = keys - REQUIRED_FIELDS
    if unknown:
        raise ValueError(f"kaynak kaydında bilinmeyen alan: {sorted(unknown)} ({entry['id']})")
    if entry["id"] in seen:
        raise ValueError(f"yinelenen kaynak id: {entry['id']}")
    if entry["access_basis"] not in VALID_ACCESS_BASES:
        raise ValueError(
            f"kaynak kaydında geçersiz access_basis: {entry['access_basis']!r} ({entry['id']})"
        )


def load_sources(path: Path) -> tuple[Source, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "sources" not in raw:
        raise ValueError(f"{path}: kökte 'sources' anahtarı yok")
    sources: tuple[Source, ...] = ()
    seen: frozenset[str] = frozenset()
    for entry in raw["sources"]:
        _validate(entry, seen)
        sources = (
            *sources,
            Source(**{**entry, "declared_paths": tuple(entry["declared_paths"])}),
        )
        seen = seen | {entry["id"]}
    return sources


def enabled_sources(sources: tuple[Source, ...]) -> tuple[Source, ...]:
    return tuple(entry for entry in sources if entry.enabled)


def robots_snapshot(source: Source, robots_dir: Path) -> Path:
    return robots_dir / f"{source.id}.txt"


def robots_for(source: Source, robots_dir: Path) -> RobotFileParser:
    """Commit'lenmiş robots.txt anlık görüntüsünü ayrıştırır.

    `parse()` ÇAĞRILMAZSA `can_fetch` her yola False der (CPython: "until the robots.txt file
    has been read ... we must assume that no url is allowable"). Boş gövdeyle parse edilince
    ise True döner. İkisi farklıdır: biri "bilmiyoruz", diğeri "kısıt yok". Boş dosya, ölçülmüş
    ve boş çıkmış bir politikadır (TFF'de robots.txt 404, ClubElo'nunki boş) — ve parse edilir.

    BOŞ SATIRLAR ELENİR — R7 incelemesinde bulundu. `RobotFileParser.parse()` state==2
    (en az bir Disallow/Allow görülmüş) İKEN boş bir satıra rastlarsa, o bloğu YENİ bir
    `User-agent:` satırı GÖRMEDEN bitmiş sayar; sonraki Disallow/Allow satırları hiçbir
    gruba eklenmez, SESSİZCE atılır. RFC 9309'da bir grup yalnız YENİ bir User-agent
    satırıyla (ya da EOF'ta) biter — boş satır kozmetiktir. Wikidata'nın gerçek robots.txt'i
    (446 satır, 148'den sonra TEK "User-agent: *" satırı) tam bunu yapıyor: satır 422/423/425
    boş, 435-436'daki `Disallow: /wiki/Special:EntityData/` + `Allow: /wiki/Special:EntityData/
    *.` satırları BLOKA HİÇ EKLENMİYORDU (ölçüldü: boş satırlar elenmeden `default_entry.
    rulelines`'ta "EntityData" geçen TEK satır yoktu). Boş satırları eleyerek stdlib'in kendi
    state machine'i grubu doğru biçimde SÜRDÜRÜYOR.
    """
    raw_lines = robots_snapshot(source, robots_dir).read_text(encoding="utf-8").splitlines()
    non_blank_lines = [line for line in raw_lines if line.strip() != ""]
    parser = RobotFileParser()
    parser.parse(non_blank_lines)
    return parser


def allows(parser: RobotFileParser, source: Source, path: str) -> bool:
    """`path` bu kaynağın robots.txt'i altında istenebilir mi?

    `access_basis=api_terms` KAYNAKLARDA robots.txt HİÇ SORULMAZ — R8: Robots Exclusion
    Protocol tarayıcıları hedefler (spec §3.2/1), belgelenmiş bir API'nin istemcisini değil;
    o kaynağın erişim gerekçesi kendi ToS'udur (§3.2/3), `Source.terms_url`de tutulur ve
    varlığı `audit_offline`de ayrıca zorlanır. `parser` argümanı bu dalda KULLANILMAZ —
    imza `robots_for()`ın döndürdüğü tipe uysun diye hâlâ alınır.

    BİLİNEN SINIR (robots-tabanlı kaynaklarda): `urllib.robotparser` `*`/`$` joker karakter
    uzantısını (Google/Bing'in de-facto standardı) UYGULAMAZ — yalnız orijinal 1996
    taslağının DÜZ ÖNEK eşleşmesini yapar. `RuleLine` her deseni `urllib.parse.quote`'tan
    geçirir; bu `*` ve `?`yi `%2A`/`%3F`ye çevirir, yani `Disallow: /*.php` gerçek bir
    istekte HİÇBİR ZAMAN eşleşmeyen düz bir dizeye döner (ölçüldü: `config/robots/
    footystats.txt` ve `ajansspor.txt`'nin gerçek gövdesi tam olarak bu deseni taşıyor —
    bkz. Task 3 raporu). AYRICA: birden çok kural aynı yola uyduğunda `RobotFileParser`
    DOSYA SIRASINDAKİ İLK eşleşeni kullanır, RFC 9309'un "en UZUN/en ÖZGÜL eşleşen kural
    kazanır" kuralını DEĞİL — yani daha sonra gelen, daha özgül bir `Allow`, daha önce gelen
    geniş bir `Disallow`u asla geçemez (ölçüldü: wikidata'nın `/wiki/Special:EntityData/*.`
    Allow'u tam bunun kurbanı — bkz. DEFERRED §5.5). Yalnız düz önekli VE ÇAKIŞMAYAN
    `Disallow` satırları güvenilir biçimde zorlanır. Bu, yeni bağımlılık eklemeden stdlib'in
    kendi sınırıdır; joker-duyarlı/en-özgül-kazanır bir ayrıştırıcı (ör. `protego`)
    eklenene kadar `declared_paths`e bu tuzaklara düşen bir yol ekleyip "kapı zaten yakalar"
    varsaymayın.
    """
    if source.access_basis == ACCESS_BASIS_API_TERMS:
        return True
    return bool(parser.can_fetch(source.user_agent, f"{source.base_url}{path}"))


def guard_path(parser: RobotFileParser, source: Source, path: str) -> None:
    if not allows(parser, source, path):
        raise SourceBlocked(f"{source.id}: robots.txt '{path}' yolunu kapatıyor — istek atılmadı")


def audit_offline(
    sources: tuple[Source, ...],
    robots_dir: Path,
    today: date,
    *,
    max_age_days: int = 30,
) -> tuple[str, ...]:
    """Ağ GEREKTİRMEYEN kaynak politikası denetimi; ihlal metinlerini döner.

    Kapının bu adımı her push'ta koşar, secret istemez ve ağa çıkmaz. Canlı sapmayı
    `sources-audit.yml` günde bir ölçer. Sözleşme kapıda, sapma zamanlanmış işte —
    `snapshot`/`seal` ayrımının aynısı.

    `access_basis=api_terms` kaynaklarda robots kontrolü (anlık görüntü/tazelik/
    beyan-edilen-yol) hâlâ koşar — o üçü YALNIZ robots.txt'in DENETİM İZİNİ tazeliyor,
    erişim kararını değil (bkz. `allows()`). Erişim kararı için tek yeni sınama: `terms_url`
    var mı.
    """
    violations: tuple[str, ...] = ()
    for source in enabled_sources(sources):
        # access_basis=api_terms İÇİN ZORUNLU GEREKÇE: istisna dipnot olarak kaybolamaz.
        # `allows()` zaten bu kaynaklarda robots'u sormuyor (aşağıdaki döngü no-op'tur) —
        # burada denetlenen SPESİFİK olarak terms_url'in VAR OLDUĞUdur, robots içeriği değil.
        if source.access_basis == ACCESS_BASIS_API_TERMS and not source.terms_url:
            violations = (
                *violations,
                f"{source.id}: access_basis=api_terms ama terms_url yok — istisna gerekçesiz",
            )
        snapshot = robots_snapshot(source, robots_dir)
        if not snapshot.is_file():
            violations = (*violations, f"{source.id}: robots anlık görüntü yok ({snapshot})")
            continue
        if today - source.robots_verified_at > timedelta(days=max_age_days):
            violations = (
                *violations,
                f"{source.id}: robots doğrulaması {max_age_days} günden eski "
                f"({source.robots_verified_at})",
            )
        parser = robots_for(source, robots_dir)
        for path in source.declared_paths:
            if not allows(parser, source, path):
                violations = (*violations, f"{source.id}: beyan edilen yol robots'a aykırı: {path}")
    return violations
