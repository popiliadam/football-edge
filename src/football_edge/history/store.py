"""`hist_files` (önbellek, yol başına son sürüm) ve `hist_fetches` (append-only çekme günlüğü).

`hist_files` kanıt DEĞİLDİR (tasarım D6): kanıt, çekme günlüğü ile depodaki kilittir. İçerik
gzip'le saklanır; `sha256` ve `byte_size` AÇILMIŞ baytlarındır. Ham üçüncü taraf içeriği yalnız bu
özel tabloda durur — bu modül onu loga yazmaz.
"""

from __future__ import annotations

import gzip
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

import psycopg

from football_edge.collector import ContractViolation

_CURRENT_SHA = "SELECT sha256 FROM hist_files WHERE path = %s"
_UPSERT_FILE = """
    INSERT INTO hist_files
      (path, sha256, fetched_at, http_last_modified, byte_size, row_count, content)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (path) DO UPDATE SET
      sha256 = excluded.sha256,
      fetched_at = excluded.fetched_at,
      http_last_modified = excluded.http_last_modified,
      byte_size = excluded.byte_size,
      row_count = excluded.row_count,
      content = excluded.content
"""
_INSERT_FETCH = """
    INSERT INTO hist_fetches
      (path, fetched_at, sha256, http_status, rows_parsed, rows_rejected)
    VALUES (%s, %s, %s, %s, %s, %s)
"""
_LOAD_FILES = "SELECT path, sha256, fetched_at, content FROM hist_files WHERE path = ANY(%s)"


@dataclass(frozen=True)
class CachedFile:
    path: str
    sha256: str
    fetched_at: datetime
    content: bytes  # açılmış (gzip değil)


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def save_file(
    conn: psycopg.Connection[Any],
    *,
    path: str,
    content: bytes,
    fetched_at: datetime,
    last_modified: str | None,
    row_count: int,
) -> bool:
    """İçerik değiştiyse (ya da yol yeniyse) satırı yazar ve True döner.

    Aynı içerik yeniden YAZILMAZ: `fetched_at` o sürümün İLK görüldüğü anı taşır; her çekmenin
    anı `hist_fetches`tedir. Commit çağıranındır.
    """
    digest = sha256_hex(content)
    with conn.cursor() as cur:
        cur.execute(_CURRENT_SHA, (path,))
        found = cur.fetchone()
        if found is not None and found[0] == digest:
            return False
        cur.execute(
            _UPSERT_FILE,
            (
                path,
                digest,
                fetched_at,
                last_modified,
                len(content),
                row_count,
                gzip.compress(content, mtime=0),
            ),
        )
    return True


def log_fetch(
    conn: psycopg.Connection[Any],
    *,
    path: str,
    fetched_at: datetime,
    sha256: str | None,
    http_status: int | None,
    rows_parsed: int,
    rows_rejected: int,
) -> None:
    """Her çekme denemesi bir satır; `sha256` NULL ise dosya önbelleğe GİRMEDİ. Commit çağıranın."""
    with conn.cursor() as cur:
        cur.execute(
            _INSERT_FETCH, (path, fetched_at, sha256, http_status, rows_parsed, rows_rejected)
        )


def _cached(row: Sequence[Any]) -> CachedFile:
    path, digest, fetched_at, stored = row
    content = gzip.decompress(bytes(stored))
    if sha256_hex(content) != digest:
        raise ContractViolation(f"{path}: önbellekteki içerik kayıtlı sha256'yı üretmiyor")
    return CachedFile(path=path, sha256=digest, fetched_at=fetched_at, content=content)


def load_files(conn: psycopg.Connection[Any], paths: Sequence[str]) -> Mapping[str, CachedFile]:
    """İstenen yollardan önbellekte OLANLAR; eksik yolun kararı çağıranındır."""
    with conn.cursor() as cur:
        cur.execute(_LOAD_FILES, (list(paths),))
        rows = cur.fetchall()
    return MappingProxyType({row[0]: _cached(row) for row in rows})
