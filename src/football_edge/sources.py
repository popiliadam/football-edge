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
    """
    parser = RobotFileParser()
    parser.parse(robots_snapshot(source, robots_dir).read_text(encoding="utf-8").splitlines())
    return parser


def allows(parser: RobotFileParser, source: Source, path: str) -> bool:
    """`path` bu kaynağın robots.txt'i altında istenebilir mi?

    BİLİNEN SINIR: `urllib.robotparser` `*`/`$` joker karakter uzantısını (Google/Bing'in
    de-facto standardı) UYGULAMAZ — yalnız orijinal 1996 taslağının DÜZ ÖNEK eşleşmesini
    yapar. `RuleLine` her deseni `urllib.parse.quote`'tan geçirir; bu `*` ve `?`yi
    `%2A`/`%3F`ye çevirir, yani `Disallow: /*.php` gerçek bir istekte HİÇBİR ZAMAN
    eşleşmeyen düz bir dizeye döner (ölçüldü: `config/robots/footystats.txt` ve
    `ajansspor.txt`'nin gerçek gövdesi tam olarak bu deseni taşıyor — bkz. Task 3 raporu).
    Yalnız düz önekli `Disallow` satırları (ör. `/wiki/Special:`, `/lineup/` — joker YOK)
    güvenilir biçimde zorlanır. Bu, yeni bağımlılık eklemeden (bu görevin kısıtı) stdlib'in
    kendi sınırıdır; joker-duyarlı bir ayrıştırıcı (ör. `protego`) eklenene kadar
    `declared_paths`e joker karakterli bir düzen ekleyip "kapı zaten yakalar" varsaymayın.
    """
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
    """
    violations: tuple[str, ...] = ()
    for source in enabled_sources(sources):
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
