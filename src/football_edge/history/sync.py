"""football-data senkronu: çekme → doğrulama → önbellek; önbellekten maç yükleme (tasarım §4.1).

İstek yolu YALNIZ `collector._guarded_get`tir: robots her yolda ve yönlendirmenin her
sıçramasında sorulur, istekler arası `crawl_delay_seconds` beklenir. Beyan edilmemiş bir yol
istenmez (R7): `declared_paths` gerçekten çekilen yollardır.

Bir dosyanın arızası ötekileri durdurmaz ama SESSİZ de geçmez: `SyncReport.failed` onu nedeniyle
taşır ve CLI turu kırmızıya çevirir (Ruling 6).

Holdout satırları bu paketten anahtarsız ÇIKMAZ (R96): `load_matches` geliştirme ve sonrası
dönemlerini verir, holdout'u yalnız `open_holdout`un kurduğu anahtarla. Bütün dönemleri dönen
`_load_all` modüle özeldir; onu yalnız kilit komutu (`history/__main__.py`) anar — Task 3'ün AST
kuralı (`tests/test_holdout_access_rule.py`) başka her anmayı kırmızıya çevirir.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType
from typing import Any

import httpx
import psycopg
from protego import Protego

from football_edge.collector import ContractViolation, _guarded_get
from football_edge.history.catalog import (
    EXTRA,
    Catalog,
    HistoryLeague,
    declared_paths,
    file_paths,
    season_of_path,
)
from football_edge.history.football_data import check_quality, parse_file
from football_edge.history.holdout import DEV, HOLDOUT, POST, HoldoutKey, select_periods
from football_edge.history.lock import HistoryLock, verify_lock
from football_edge.history.store import load_files, log_fetch, save_file, sha256_hex
from football_edge.history.types import HistMatch
from football_edge.sources import Source, SourceBlocked

LOGGER = logging.getLogger("football_edge.history.sync")

SOURCE_ID: str = "football-data"
TIMEOUT_SECONDS = 60.0
# Saati olmayan maç (2019/20 öncesi ana ligler) aynı günün saatlilerinden önce sıralanır.
_NO_KICKOFF = datetime.min.replace(tzinfo=UTC)
# Anahtarsız okunabilen dönemler; HOLDOUT yalnız geçerli bir `HoldoutKey` ile eklenir.
_OPEN_PERIODS = frozenset({DEV, POST})


@dataclass(frozen=True)
class SyncReport:
    requested: int
    changed: int
    unchanged: int
    failed: tuple[tuple[str, str], ...]  # (yol, neden)
    rejected_rows: int


@dataclass(frozen=True)
class _Synced:
    changed: bool
    rejected: int


def mutable_paths(catalog: Catalog) -> tuple[str, ...]:
    """Hâlâ değişebilen dosyalar: güncel sezonun ana lig dosyaları ve bütün ek lig dosyaları."""
    return tuple(
        sorted(
            file_paths(league, current_season=catalog.current_season)[-1]
            for league in catalog.leagues
        )
    )


def _league_of(catalog: Catalog, path: str) -> HistoryLeague:
    for league in catalog.leagues:
        if path in file_paths(league, current_season=catalog.current_season):
            return league
    raise ContractViolation(f"{SOURCE_ID}: {path} katalogda yok")


def _season_for(league: HistoryLeague, path: str) -> str | None:
    return None if league.kind == EXTRA else season_of_path(path)


def _sync_one(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    *,
    source: Source,
    parser: Protego,
    catalog: Catalog,
    path: str,
    fetched_at: datetime,
) -> _Synced:
    if path not in source.declared_paths:
        raise SourceBlocked(f"{source.id}: {path} declared_paths'te yok — istek atılmadı")
    league = _league_of(catalog, path)
    season = _season_for(league, path)
    response = _guarded_get(client, source, path, parser, timeout=TIMEOUT_SECONDS)
    result = parse_file(response.content, league=league, season=season)
    if result.trimmed_rows:
        # R111 kırpması sessiz geçmez; yalnız sayı — hücre değeri loga girmez (Ruling 4).
        LOGGER.info(
            "yol=%s: %d kaydın sondaki boş fazla hücreleri kırpıldı", path, result.trimmed_rows
        )
    check_quality(result, path=path, league=league, season=season)
    changed = save_file(
        conn,
        path=path,
        content=response.content,
        fetched_at=fetched_at,
        last_modified=response.headers.get("last-modified"),
        row_count=len(result.matches),
    )
    log_fetch(
        conn,
        path=path,
        fetched_at=fetched_at,
        sha256=sha256_hex(response.content),
        http_status=response.status_code,
        rows_parsed=len(result.matches),
        rows_rejected=len(result.rejected),
    )
    conn.commit()
    return _Synced(changed=changed, rejected=len(result.rejected))


def _reason(error: Exception) -> str:
    return " ".join(f"{type(error).__name__}: {error}".split())


def _record_failure(
    conn: psycopg.Connection[Any], *, path: str, fetched_at: datetime, error: Exception
) -> None:
    """Başarısız deneme de günlüğe girer — istek hiç atılmamış olsa bile (robots, beyan):
    sha256 NULL, yani önbelleğe girmedi; http_status yalnız HTTP hatasında dolu."""
    status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
    log_fetch(
        conn,
        path=path,
        fetched_at=fetched_at,
        sha256=None,
        http_status=status,
        rows_parsed=0,
        rows_rejected=0,
    )
    conn.commit()


def sync(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    *,
    source: Source,
    parser: Protego,
    catalog: Catalog,
    paths: Sequence[str],
    now: Callable[[], datetime],
) -> SyncReport:
    done: tuple[_Synced, ...] = ()
    failed: tuple[tuple[str, str], ...] = ()
    for path in paths:
        fetched_at = now()
        try:
            synced = _sync_one(
                conn,
                client,
                source=source,
                parser=parser,
                catalog=catalog,
                path=path,
                fetched_at=fetched_at,
            )
        except Exception as error:
            # Sayaçlar yalnız commit'ten SONRA artar: düşen commit "yazıldı" sayılmaz (G1).
            conn.rollback()
            LOGGER.exception("yol=%s senkronlanamadı, diğerlerine devam", path)
            _record_failure(conn, path=path, fetched_at=fetched_at, error=error)
            failed = (*failed, (path, _reason(error)))
            continue
        done = (*done, synced)
    changed = sum(1 for entry in done if entry.changed)
    return SyncReport(
        requested=len(paths),
        changed=changed,
        unchanged=len(done) - changed,
        failed=failed,
        rejected_rows=sum(entry.rejected for entry in done),
    )


def _order(match: HistMatch) -> tuple[date, datetime, str]:
    return (match.date, match.kickoff or _NO_KICKOFF, match.home)


def _parsed(path: str, content: bytes, league: HistoryLeague) -> tuple[HistMatch, ...]:
    season = _season_for(league, path)
    result = parse_file(content, league=league, season=season)
    check_quality(result, path=path, league=league, season=season)
    return result.matches


def _load_all(
    conn: psycopg.Connection[Any], catalog: Catalog
) -> Mapping[str, tuple[HistMatch, ...]]:
    """Lig kodu → bütün sezonların BÜTÜN dönemleri (holdout dahil), (tarih, başlama, ev) sırasıyla.

    Modüle özel (R96): yalnız `load_matches` ve kilit komutu anar. Önbellekte eksik dosya varsa ya
    da bir dosya bugünkü sözleşmeyi geçmiyorsa `ContractViolation`: eksik veriyle kurulan bir kilit
    ya da doğrulama başarı gibi görünürdü.
    """
    paths = declared_paths(catalog)
    files = load_files(conn, paths)
    missing = [path for path in paths if path not in files]
    if missing:
        raise ContractViolation(
            f"{SOURCE_ID}: önbellekte {len(missing)} dosya yok (ilki {missing[0]}) — "
            "önce `sync --all`"
        )
    return MappingProxyType(
        {
            league.code: tuple(
                sorted(
                    (
                        match
                        for path in file_paths(league, current_season=catalog.current_season)
                        for match in _parsed(path, files[path].content, league)
                    ),
                    key=_order,
                )
            )
            for league in catalog.leagues
        }
    )


class DuplicateMatches(ContractViolation):
    """Aynı (lig, tarih, ev, deplasman) BÜTÜN dönemlerde (holdout dahil) iki kez geçti.

    Faz 3 plan incelemesi C1: yineleme yalnız oynatmada yakalansaydı holdout'taki bir yineleme
    açılıştan SONRA patlar ve tek açılışı harcardı. Denetim anahtar yokken, burada koşar; mesaj
    holdout satırını (tarih, ad) dışarı vermez — yalnız lig ve sayı.
    """


def _refuse_duplicates(everything: Mapping[str, Sequence[HistMatch]]) -> None:
    found = {
        code: sum(n - 1 for n in Counter((m.date, m.home, m.away) for m in matches).values())
        for code, matches in everything.items()
    }
    repeated = {code: count for code, count in sorted(found.items()) if count}
    if repeated:
        detail = ", ".join(f"{code} ×{count}" for code, count in repeated.items())
        raise DuplicateMatches(f"{SOURCE_ID}: yinelenen maç (bütün dönemler, 14g): {detail}")


def load_matches(
    conn: psycopg.Connection[Any],
    catalog: Catalog,
    *,
    lock: HistoryLock | None = None,
    key: HoldoutKey | None = None,
) -> Mapping[str, tuple[HistMatch, ...]]:
    """Lig kodu → geliştirme + sonrası dönemleri; holdout yalnız `open_holdout`un anahtarıyla (R96).

    `lock` verilirse doğrulama süzgeçten ÖNCE, bütün satırlar üzerinde koşar: değişen bir holdout
    satırı da `LockViolation` verir, oysa o satır hiç dışarı verilmez. Elle kurulan anahtar
    `select_periods`te `HoldoutLocked` verir.
    """
    everything = _load_all(conn, catalog)
    _refuse_duplicates(everything)
    if lock is not None:
        verify_lock(lock, everything)
    periods = _OPEN_PERIODS if key is None else _OPEN_PERIODS | {HOLDOUT}
    return MappingProxyType(
        {
            code: select_periods(matches, periods=periods, key=key)
            for code, matches in everything.items()
        }
    )
