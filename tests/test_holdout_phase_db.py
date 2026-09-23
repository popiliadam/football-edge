"""0010'un tekil indeksi GERÇEK veritabanında (Faz 3 tasarımı §9 G6, plan incelemesi I6).

Tek işlemde, sonunda geri alınarak: aynı fazın ikinci açılışı ve ikinci yeniden koşusu
`UniqueViolation` verir, ilk yeniden koşu kabul edilir. Faz adı `faz99` — gerçek fazlarla
karışmaz; geri alma satır bırakmaz (append-only tetikleyiciler yalnız UPDATE/DELETE/TRUNCATE'i
durdurur). `DATABASE_URL` yoksa ADIYLA atlanır (`zincir` adımı gibi); 0010 uygulanmamış bir
veritabanında KIRMIZIDIR — doğru davranış.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import psycopg
import pytest

from football_edge.db import connect

INSERT = "INSERT INTO holdout_access_log (opened_at, git_sha, purpose) VALUES (%s, %s, %s)"
NO_DATABASE = "DATABASE_URL yok — 0010 gerçek veritabanında sınanmadı"


def _rejects(cur: psycopg.Cursor[object], purpose: str, savepoint: str) -> bool:
    cur.execute(f"SAVEPOINT {savepoint}")
    try:
        cur.execute(INSERT, (datetime.now(UTC), "a" * 40, purpose))
    except psycopg.errors.UniqueViolation:
        cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        return True
    return False


@pytest.mark.skipif(not os.getenv("DATABASE" + "_URL"), reason=NO_DATABASE)
def test_the_phase_index_allows_one_opening_and_one_rerun_per_phase() -> None:
    with connect() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(INSERT, (datetime.now(UTC), "a" * 40, "faz99:ilk"))
                assert _rejects(cur, "faz99:ikinci", "s1"), "ikinci faz99 açılışı kabul edildi"
                assert not _rejects(cur, "faz99-rerun:çöktü:ilk", "s2"), (
                    "ilk yeniden koşu reddedildi"
                )
                assert _rejects(cur, "faz99-rerun:yine:ilk", "s3"), (
                    "ikinci yeniden koşu kabul edildi"
                )
                assert not _rejects(cur, "faz98:başka", "s4"), "başka faz reddedildi"
        finally:
            conn.rollback()
