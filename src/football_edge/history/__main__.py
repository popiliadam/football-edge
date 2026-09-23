"""`python -m football_edge.history` — tarihsel taban CLI'ı (tasarım §4.1, §5.2).

    sync [--all]         değişken dosyalar (güncel sezon + ek ligler); --all: bütün beyanlı yollar
    lock --write PATH    önbellekten kilit dosyası üretir (geliştirme + holdout özetleri)
    lock --verify PATH   önbelleği kilide karşı doğrular; ihlal ya da bozuk kilit: exit 9

Kilit yazımı holdout satırlarının ÖZETİNE ihtiyaç duyar, satırlarına değil: bütün dönemleri dönen
`sync._load_all`ı anabilen tek modül budur (R96, Task 3'ün AST kuralı); özet dosyaya yalnız sayı ve
sha256 olarak çıkar. Doğrulama `load_matches(..., lock=)` üzerinden: holdout satırı dışarı çıkmaz.

Çıktı `logging` iledir; kök handler `collect.configure_logging` ile redakte edilir (DSN parolası
bir psycopg hatasında log'a düşmesin). Yalnız toplu sayılar yazılır, ham satır yazılmaz.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from football_edge.collect import (
    EXIT_SOURCE_FAILED,
    ROBOTS_DIR,
    SOURCES_PATH,
    configure_logging,
)
from football_edge.collector import ContractViolation
from football_edge.db import connect
from football_edge.history.catalog import Catalog, declared_paths, load_catalog
from football_edge.history.holdout import DEV, HOLDOUT
from football_edge.history.lock import (
    EXIT_LOCK_VIOLATION,
    LockViolation,
    build_lock,
    dump_lock,
    load_lock,
)
from football_edge.history.sync import (
    SOURCE_ID,
    SyncReport,
    _load_all,
    load_matches,
    mutable_paths,
    sync,
)
from football_edge.sources import Source, enabled_sources, load_sources, robots_for

LOGGER = logging.getLogger("football_edge.history")

CATALOG_PATH = Path("config/history_leagues.yaml")


def _source() -> Source:
    """`enabled: false` kapatma anahtarıdır: kayıt yoksa ya da kapalıysa çekme hiç başlamaz."""
    for entry in enabled_sources(load_sources(SOURCES_PATH)):
        if entry.id == SOURCE_ID:
            return entry
    raise RuntimeError(f"{SOURCE_ID}: kaynak kaydı yok ya da enabled=false ({SOURCES_PATH})")


def _report(report: SyncReport) -> int:
    LOGGER.info(
        "%s: %d yol istendi, %d değişti, %d aynı, %d başarısız, %d satır reddedildi",
        SOURCE_ID,
        report.requested,
        report.changed,
        report.unchanged,
        len(report.failed),
        report.rejected_rows,
    )
    for path, reason in report.failed:
        LOGGER.error("başarısız: %s — %s", path, reason)
    return EXIT_SOURCE_FAILED if report.failed else 0


def _sync_command(catalog: Catalog, *, all_paths: bool) -> int:
    source = _source()
    parser = robots_for(source, ROBOTS_DIR)
    paths = declared_paths(catalog) if all_paths else mutable_paths(catalog)
    with connect() as conn, httpx.Client() as client:
        report = sync(
            conn,
            client,
            source=source,
            parser=parser,
            catalog=catalog,
            paths=paths,
            now=lambda: datetime.now(UTC),
        )
    return _report(report)


def _write_lock(catalog: Catalog, target: Path) -> int:
    with connect() as conn:
        matches = _load_all(conn, catalog)
    lock = build_lock(matches, locked_at=datetime.now(UTC).date())
    target.write_text(dump_lock(lock), encoding="utf-8")
    for code, digests in lock.leagues.items():
        LOGGER.info("%s: dev %d, holdout %d satır", code, digests[DEV].rows, digests[HOLDOUT].rows)
    LOGGER.info("kilit yazıldı: %s (%d lig)", target, len(lock.leagues))
    return 0


def _verify_lock(catalog: Catalog, target: Path) -> int:
    """Bozuk kilit dosyası da (R99: `load_lock` → LockViolation) ve veri farkı da exit 9."""
    try:
        lock = load_lock(target)
        with connect() as conn:
            load_matches(conn, catalog, lock=lock)
    except LockViolation as violation:
        LOGGER.error("KİLİT İHLALİ: %s", violation)
        return EXIT_LOCK_VIOLATION
    LOGGER.info("kilit doğrulandı: %s (%d lig)", target, len(lock.leagues))
    return 0


def _lock_command(catalog: Catalog, *, write: Path | None, verify: Path | None) -> int:
    try:
        if write is not None:
            return _write_lock(catalog, write)
        if verify is not None:
            return _verify_lock(catalog, verify)
    except ContractViolation as violation:
        # Eksik ya da sözleşmeyi geçmeyen önbellekle kilit ne yazılır ne doğrulanır.
        LOGGER.error("önbellek kullanılamaz: %s", violation)
        return EXIT_SOURCE_FAILED
    raise ValueError("lock: --write ya da --verify gerekli")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.history")
    commands = parser.add_subparsers(dest="command", required=True)
    sync_parser = commands.add_parser("sync", help="football-data dosyalarını önbelleğe çek")
    sync_parser.add_argument(
        "--all", action="store_true", help="bütün beyanlı yollar (ilk tam yükleme)"
    )
    lock_parser = commands.add_parser("lock", help="kilit dosyasını yaz ya da doğrula")
    target = lock_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--write", type=Path, metavar="PATH")
    target.add_argument("--verify", type=Path, metavar="PATH")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    catalog = load_catalog(CATALOG_PATH)
    if args.command == "sync":
        return _sync_command(catalog, all_paths=args.all)
    return _lock_command(catalog, write=args.write, verify=args.verify)


if __name__ == "__main__":
    raise SystemExit(main())
