"""Tarihsel taban kilidi (tasarım §5.2, D8; kanonik satır: Ruling R86).

Geliştirme ve holdout dönemlerinin satırları, lig başına, satır sayısına ve kanonik satırların
sha256 özetine indirgenir; özetler `config/history_lock.yaml`da depoya girer — içerik değil, yalnız
sayı ve özet. Her yüklemede veriden yeniden hesaplanır: kaynak eski bir satırı değiştirirse
`verify_lock` farkların hepsini tek bir `LockViolation`da söyler ve karar insana düşer.

Kanonik satır AYRIŞTIRILMIŞ değerlerden kurulur (R86): kaynak metni `HistMatch`te yoktur ve
"2.10" → "2.1" gibi bir biçim farkını yanlış ihlal sayardı; değer değişikliğini ikisi de yakalar.
Biçim değişirse `CANONICAL_VERSION` artar ve kilit yeniden üretilir.

Kilit holdout makinesidir, bir açılış değildir: holdout satırları burada `period_of` ile ayrılıp
özetlenir, dışarı yalnız satır sayısı, özet ve AvgC kapsamı çıkar; satırın kendisi hiç dönmez. Bu
yüzden `HoldoutKey` kullanmaz ve `holdout_access_log`a yazmaz — holdout'u OKUYAN her yol
`select_periods` + `open_holdout`tan geçer. Sonrası dönemi kilitlenmez: her hafta büyür.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from football_edge.history.holdout import DEV, DEV_END, HOLDOUT, HOLDOUT_END, period_of
from football_edge.history.types import CLOSING, H2H, REFERENCE_BOOK, HistMatch

CANONICAL_VERSION = 1
# Kilitlenen dönemler, dosyadaki sırasıyla.
_LOCKED_PERIODS = (DEV, HOLDOUT)
# Kapsam bilgisi referans kapanıştan (D3): lig önerisi holdout doluluğunu açmadan buradan okur.
_SEPARATORS = ("\t", "\n", "\r")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ROOT_KEYS = frozenset({"canonical_version", "locked_at", "dev_end", "holdout_end", "leagues"})
_DIGEST_KEYS = frozenset({"rows", "sha256", "avgc_complete"})
_HEADER = (
    "# Tarihsel taban kilidi (tasarım §5.2, D8): `python -m football_edge.history lock --write`.",
    "# İÇERİK TAŞIMAZ: yalnız dönem başına satır sayısı, kanonik satırların sha256 özeti ve AvgC",
    "# 1X2'si tam satır sayısı. Kilitli dönemler dev ve holdout; sonrası her hafta değiştiği için",
    "# kilitlenmez. Bu dosyayı değiştirmek gerekçeli bir commit'tir (ör. kaynak eski bir skoru",
    "# düzeltti): gerekçe commit mesajına yazılır, eski özet git geçmişinde kalır.",
)


class LockViolation(RuntimeError):
    """Kilitli dönemlerin verisi kilitten farklı. Farkların HEPSİ tek istisnada, sırayla."""

    def __init__(self, *differences: str) -> None:
        self.differences = differences
        super().__init__(f"kilit ihlali — {len(differences)} fark:\n" + "\n".join(differences))


@dataclass(frozen=True)
class Digest:
    rows: int
    sha256: str
    avgc_complete: int  # AvgC 1X2'si tam satır sayısı (kapsam bilgisi)


@dataclass(frozen=True)
class HistoryLock:
    canonical_version: int
    locked_at: date
    dev_end: date
    holdout_end: date
    leagues: Mapping[str, Mapping[str, Digest]]  # kod → {DEV: Digest, HOLDOUT: Digest}


def canonical_line(match: HistMatch) -> str:
    """Kimlik ve sonuç alanları, `OddsKey` sırasıyla her fiyat (`kitap|market|sonuç|evre=repr`),
    ad sırasıyla her istatistik (`ad=değer`); sekmeyle. `source_line` girmez: dosyadaki yer
    içerik değildir, kaynak araya satır eklese eski maçların özeti değişmemeli."""
    where = f"{match.league} {match.date} satır {match.source_line}"
    if match.kickoff is not None and match.kickoff.utcoffset() is None:
        raise ValueError(f"{where}: başlama saati saat dilimsiz — özet makineye bağlı olurdu")
    kickoff = "" if match.kickoff is None else match.kickoff.astimezone(UTC).isoformat()
    fields = (
        match.league,
        match.season,
        match.date.isoformat(),
        kickoff,
        match.home,
        match.away,
        str(match.home_goals),
        str(match.away_goals),
        match.result,
        *(
            f"{key.book}|{key.market}|{key.outcome}|{key.phase}={match.odds[key]!r}"
            for key in sorted(match.odds)
        ),
        *(f"{name}={value}" for name, value in sorted(match.stats.items())),
    )
    if any(separator in value for value in fields for separator in _SEPARATORS):
        raise ValueError(f"{where}: bir değer ayraç içeriyor — kanonik satır belirsizleşirdi")
    return "\t".join(fields)


def digest(matches: Sequence[HistMatch]) -> Digest:
    """Sıradan bağımsız özet: kanonik satırlar SIRALANIP `\\n` ile birleştirilir."""
    lines = sorted(canonical_line(match) for match in matches)
    complete = sum(1 for match in matches if match.prices(REFERENCE_BOOK, H2H, CLOSING) is not None)
    return Digest(
        rows=len(lines),
        sha256=hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest(),
        avgc_complete=complete,
    )


def build_lock(
    matches_by_league: Mapping[str, Sequence[HistMatch]], *, locked_at: date
) -> HistoryLock:
    return HistoryLock(
        canonical_version=CANONICAL_VERSION,
        locked_at=locked_at,
        dev_end=DEV_END,
        holdout_end=HOLDOUT_END,
        leagues=MappingProxyType(
            {code: _period_digests(matches) for code, matches in sorted(matches_by_league.items())}
        ),
    )


def _period_digests(matches: Sequence[HistMatch]) -> Mapping[str, Digest]:
    """Dönem üyeliği kaynağın tarihiyle; holdout satırları bu fonksiyondan dışarı çıkmaz."""
    return MappingProxyType(
        {
            period: digest([match for match in matches if period_of(match.date) == period])
            for period in _LOCKED_PERIODS
        }
    )


def dump_lock(lock: HistoryLock) -> str:
    """Belirlenimci YAML: sabit anahtar sırası, sıralı lig kodları, başlık yorumu."""
    head = (
        *_HEADER,
        f"canonical_version: {lock.canonical_version}",
        f"locked_at: {lock.locked_at.isoformat()}",
        f"dev_end: {lock.dev_end.isoformat()}",
        f"holdout_end: {lock.holdout_end.isoformat()}",
        "leagues:" if lock.leagues else "leagues: {}",
    )
    body = tuple(
        line for code in sorted(lock.leagues) for line in _league_lines(code, lock.leagues[code])
    )
    return "\n".join((*head, *body)) + "\n"


def _league_lines(code: str, periods: Mapping[str, Digest]) -> tuple[str, ...]:
    return (
        f"  {code}:",
        *(
            line
            for period in _LOCKED_PERIODS
            for line in (
                f"    {period}:",
                f"      rows: {periods[period].rows}",
                f"      sha256: {periods[period].sha256}",
                f"      avgc_complete: {periods[period].avgc_complete}",
            )
        ),
    )


def load_lock(path: Path) -> HistoryLock:
    """Yapıyı, 64 haneli özetleri ve `canonical_version`ı doğrular. Her yapı ve biçim hatası tek
    farklı bir `LockViolation`dır (R99): kilidi okuyan CLI'lar veri farkındaki çıkışı (9) verir."""
    root = _fields(_read(path), _ROOT_KEYS, str(path))
    version = root["canonical_version"]
    if type(version) is not int or version != CANONICAL_VERSION:
        raise LockViolation(
            f"{path}: canonical_version {version!r}, kod {CANONICAL_VERSION} bekliyor — kilit "
            "başka bir kanonik biçimle üretilmiş, yeniden üretilmeli"
        )
    return HistoryLock(
        canonical_version=version,
        locked_at=_day(root["locked_at"], f"{path}: locked_at"),
        dev_end=_day(root["dev_end"], f"{path}: dev_end"),
        holdout_end=_day(root["holdout_end"], f"{path}: holdout_end"),
        leagues=_leagues(root["leagues"], f"{path}: leagues"),
    )


def _read(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        # Hata metni çok satırlı olabilir; farklar satır başına bir tanedir.
        reason = " ".join(str(error).split())
        raise LockViolation(f"{path}: kilit dosyası okunamıyor ({reason})") from error


def _fields(raw: object, keys: frozenset[str], where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise LockViolation(f"{where}: eşleme bekleniyordu, {type(raw).__name__} geldi")
    missing = sorted(keys - raw.keys())
    unknown = sorted(str(key) for key in raw.keys() - keys)
    if missing or unknown:
        raise LockViolation(f"{where}: eksik alan {missing}, bilinmeyen alan {unknown}")
    return raw


def _leagues(raw: object, where: str) -> Mapping[str, Mapping[str, Digest]]:
    if not isinstance(raw, dict):
        raise LockViolation(f"{where}: lig kodu → dönem eşlemesi bekleniyordu")
    codes = tuple(raw)
    if not all(isinstance(code, str) and code for code in codes):
        raise LockViolation(f"{where}: lig kodları boş olmayan metin olmalı: {codes!r}")
    return MappingProxyType(
        {code: _periods(raw[code], f"{where}.{code}") for code in sorted(codes)}
    )


def _periods(raw: object, where: str) -> Mapping[str, Digest]:
    fields = _fields(raw, frozenset(_LOCKED_PERIODS), where)
    return MappingProxyType(
        {period: _digest_entry(fields[period], f"{where}.{period}") for period in _LOCKED_PERIODS}
    )


def _digest_entry(raw: object, where: str) -> Digest:
    fields = _fields(raw, _DIGEST_KEYS, where)
    rows = _count(fields["rows"], f"{where}.rows")
    complete = _count(fields["avgc_complete"], f"{where}.avgc_complete")
    sha = fields["sha256"]
    if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
        raise LockViolation(f"{where}.sha256: 64 küçük harfli onaltılık karakter olmalı")
    if complete > rows:
        raise LockViolation(f"{where}: avgc_complete ({complete}) satır sayısını ({rows}) aşamaz")
    return Digest(rows=rows, sha256=sha, avgc_complete=complete)


def _count(value: object, where: str) -> int:
    # `bool` bir `int` alt sınıfıdır: `rows: true` sayı yerine geçmesin.
    if type(value) is int and value >= 0:
        return value
    raise LockViolation(f"{where}: negatif olmayan tam sayı olmalı: {value!r}")


def _day(value: object, where: str) -> date:
    # `datetime` bir `date` alt sınıfıdır: saatli bir değer tarih yerine geçmesin.
    if type(value) is date:
        return value
    raise LockViolation(f"{where}: YYYY-AA-GG tarihi olmalı: {value!r}")


def verify_lock(lock: HistoryLock, matches_by_league: Mapping[str, Sequence[HistMatch]]) -> None:
    """Kilitli dönemleri veriden yeniden hesaplar; farkların HEPSİ tek `LockViolation`da: kod
    sabitlerinden farklı dönem sınırı ya da sürüm, özeti değişen (lig, dönem), kilitte olmayan lig,
    veride olmayan kilitli lig."""
    codes = sorted(set(lock.leagues) | set(matches_by_league))
    differences = (
        *_header_differences(lock),
        *(
            difference
            for code in codes
            for difference in _league_differences(
                code, lock.leagues.get(code), matches_by_league.get(code)
            )
        ),
    )
    if differences:
        raise LockViolation(*differences)


def _header_differences(lock: HistoryLock) -> tuple[str, ...]:
    pairs: tuple[tuple[str, object, object], ...] = (
        ("canonical_version", lock.canonical_version, CANONICAL_VERSION),
        ("dev_end", lock.dev_end, DEV_END),
        ("holdout_end", lock.holdout_end, HOLDOUT_END),
    )
    return tuple(
        f"{name}: kilit {locked}, kod {code}" for name, locked, code in pairs if locked != code
    )


def _league_differences(
    code: str, locked: Mapping[str, Digest] | None, matches: Sequence[HistMatch] | None
) -> tuple[str, ...]:
    if locked is None:
        return (f"{code}: veride var, kilitte yok",)
    if matches is None:
        return (f"{code}: kilitte var, veride yok",)
    actual = _period_digests(matches)
    return tuple(
        f"{code}/{period}: beklenen {_described(locked.get(period))} · "
        f"gerçek {_described(actual[period])}"
        for period in _LOCKED_PERIODS
        if locked.get(period) != actual[period]
    )


def _described(value: Digest | None) -> str:
    if value is None:
        return "yok"
    return f"rows={value.rows} sha256={value.sha256} avgc_complete={value.avgc_complete}"
