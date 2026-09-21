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
    # #M13 (deferred, Faz 1 SON inceleme'de kapatıldı): `declared_paths` bir LİSTE olmalı.
    # YAML'da skaler bir dize yazılırsa (`declared_paths: /foo/xg`, tırnaksız liste yerine)
    # `load_sources`teki `tuple(entry["declared_paths"])` onu KARAKTERLERE böler — `/`, `f`,
    # `o`, `o`, ... — ve kapı bu "yolları" robots'a karşı sessizce, anlamsızca sorar. Liste
    # DIŞINDA (dict, int, None, ...) her tip de aynı şekilde reddedilir.
    if not isinstance(entry["declared_paths"], list):
        raise ValueError(
            f"kaynak kaydında declared_paths LİSTE olmalı, "
            f"{type(entry['declared_paths']).__name__} değil ({entry['id']})"
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


# 404/410 = politika dosyası GERÇEKTEN YOK — ölçülmüş ve boş çıkmış bir sonuçtur (tff'nin
# commit'lenmiş anlık görüntüsü tam bunun kaydı). BAŞKA HİÇBİR non-200 bununla AYNI ŞEY
# DEĞİLDİR: 403/429/5xx kaynağın bizi REDDETTİĞİ anlamına gelebilir. İkisini karıştırmak
# "kapandı"yı "ölçülemedi"ye indirger (review Important #1: scripts/robots_drift.py eskiden
# HER non-200'ü boş metne düşürüyordu — bizi engelleyen bir kaynak "sapma yok" ya da "tüm
# politika silinmiş" (yanlış yön) diye raporlanıyordu).
_NO_POLICY_FILE_STATUS_CODES = (404, 410)


def snapshot_from_status(status_code: int, body: str) -> str | None:
    """Bir HTTP yanıtını robots.txt POLİTİKASINA çevirir — ya da ÖLÇÜLEMEDİYSE `None`.

    Bu, `scripts/robots_drift.py`'nin canlı ölçüm turunda kullandığı karar mantığıdır
    (kaynak-politikası bu kaynak kadar önemli, review R15: "en yeni güvenlik-ilişkili
    dal" `src/`'in DIŞINDaydı — artık değil, ve bu fonksiyon `tests/test_sources.py`'de
    sıradan test edilen kod hâline geliyor, canlı ağa çıkan bir betiğin elle doğrulanan
    çıktısına güvenmek yerine).

    - `200` → GÖVDE aynen döner (ölçülmüş, gerçek politika).
    - `404`/`410` → BOŞ metin döner (ölçülmüş, politika dosyası YOK — `robots_for`'daki
      "ölçüldü, kısıt yok" ile aynı anlam).
    - Başka HERHANGİ bir durum → `None` (ÖLÇÜLEMEDİ). Asla sessizce boş metne düşürülmez;
      çağıran bunu adıyla raporlamalı ve turu kırmızı vermelidir — geçmek değildir.
    """
    if status_code == 200:
        return body
    if status_code in _NO_POLICY_FILE_STATUS_CODES:
        return ""
    return None


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


def _date_violation(
    source_id: str, verified_at: date, today: date, max_age_days: int
) -> str | None:
    """`verified_at` GEÇERLİ bir ölçüm tarihi mi — ne GELECEKTE (bir hatıra ölçüm olamaz,
    `today - verified_at` negatifken tazelik kontrolü sessizce söner — review) ne de
    `max_age_days`den ESKİ. İkisi birden olamaz; en fazla bir ihlal döner."""
    if verified_at > today:
        return (
            f"{source_id}: robots doğrulama tarihi gelecekte ({verified_at}) "
            "— bir hatıra ölçüm olamaz"
        )
    if today - verified_at > timedelta(days=max_age_days):
        return f"{source_id}: robots doğrulaması {max_age_days} günden eski ({verified_at})"
    return None


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
        # #M20 (deferred, Faz 1 SON inceleme'de kapatıldı): `enabled: true` + boş
        # `declared_paths` bugüne kadar bu denetimden HİÇBİR ŞEY ÖLÇMEDEN geçiyordu —
        # aşağıdaki `for path in source.declared_paths` döngüsü boş demette no-op'tur, yani
        # "TEMİZ" raporu hiçbir yolu robots'a karşı sınamadan verilirdi. Yalnız
        # `access_basis=robots` kaynaklarda: `api_terms` kaynaklarda `declared_paths` zaten
        # robots kararını etkilemiyor (`allows()`), boşluğu ayrı bir ihlal SAYMAZ.
        if source.access_basis == ACCESS_BASIS_ROBOTS and not source.declared_paths:
            violations = (
                *violations,
                f"{source.id}: enabled ama declared_paths boş — hiçbir yol denetlenmiyor",
            )
        snapshot = robots_snapshot(source, robots_dir)
        if not snapshot.is_file():
            violations = (*violations, f"{source.id}: robots anlık görüntü yok ({snapshot})")
            continue
        date_violation = _date_violation(source.id, source.robots_verified_at, today, max_age_days)
        if date_violation is not None:
            violations = (*violations, date_violation)
        parser = robots_for(source, robots_dir)
        for path in source.declared_paths:
            if not allows(parser, source, path):
                violations = (*violations, f"{source.id}: beyan edilen yol robots'a aykırı: {path}")
    return violations
