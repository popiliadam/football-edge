from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from protego import Protego


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


def robots_for(source: Source, robots_dir: Path) -> Protego:
    """Commit'lenmiş robots.txt anlık görüntüsünü ayrıştırır.

    `Protego.parse("")` (boş gövde) her yola izin verir — "ölçüldü, kısıt yok" (TFF'de
    robots.txt 404 → boş anlık görüntü, ClubElo'nunki de boş). Bu satır bu ayrımı hiçbir
    zaman "hiç ölçülmedi" ile karıştırmaz — "hiç ölçülmedi" (anlık görüntü dosyası hiç
    yok) `audit_offline`'ın AYRI, dosya varlığına bakan kontrolüdür; `robots_for` yalnız
    dosya VARSA çağrılır (ölçüldü, doğrulandı: bkz. `test_empty_robots_file_allows_
    everything`).

    `protego` (Scrapy ekibinin RFC 9309 uyumlu ayrıştırıcısı — R10) kullanılıyor, stdlib
    `urllib.robotparser` DEĞİL: stdlib joker karakteri (`*`/`$`) desteklemiyordu VE çakışan
    kurallarda dosya sırasındaki ilk eşleşeni kullanıyordu, RFC 9309'un "en uzun/en özgül
    kazanır" kuralını değil — iki bağımsız, ÖLÇÜLMÜŞ kusur (eski DEFERRED §5.5, artık
    kapatıldı). Üçüncü, bağımsız bir stdlib kusuru da vardı: `RobotFileParser.parse()`
    bir bloğun kural birikimini YENİ bir `User-agent:` satırı görmeden, yalnızca boş bir
    satırla kesiyordu (RFC 9309'a aykırı). `protego` üçünü de doğru yapıyor (ölçüldü —
    bkz. `test_wildcard_disallow_actually_blocks_a_matching_path`,
    `test_longest_match_lets_a_narrow_allow_override_a_broad_disallow`,
    `test_blank_line_mid_block_does_not_drop_the_rule_that_follows`); eski, stdlib'e özel
    boş-satır-eleme önlemi bu yüzden KALDIRILDI — protego'da gereksizdi.
    """
    body = robots_snapshot(source, robots_dir).read_text(encoding="utf-8")
    return Protego.parse(body)


def allows(parser: Protego, source: Source, path: str) -> bool:
    """`path` bu kaynağın robots.txt'i altında istenebilir mi?

    `access_basis=api_terms` KAYNAKLARDA robots.txt HİÇ SORULMAZ — R8: Robots Exclusion
    Protocol tarayıcıları hedefler (spec §3.2/1), belgelenmiş bir API'nin istemcisini değil;
    o kaynağın erişim gerekçesi kendi ToS'udur (§3.2/3), `Source.terms_url`de tutulur ve
    varlığı `audit_offline`de ayrıca zorlanır. `parser` argümanı bu dalda KULLANILMAZ —
    imza `robots_for()`ın döndürdüğü tipe uysun diye hâlâ alınır.

    Joker karakter (`*`/`$`) ve çakışan kurallarda en-uzun/en-özgül-kazanır artık DOĞRU
    işleniyor (`protego`, R10 — bkz. `robots_for()`). `RuleLine.applies_to` çağrılmaz;
    `can_fetch`in argüman SIRASI stdlib'inkinin TERSİDİR (`url` önce, `user_agent` sonra)
    — burada isimli argümanla verilir, sırayla değil, tam bu yüzden.
    """
    if source.access_basis == ACCESS_BASIS_API_TERMS:
        return True
    return bool(parser.can_fetch(url=f"{source.base_url}{path}", user_agent=source.user_agent))


def guard_path(parser: Protego, source: Source, path: str) -> None:
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
