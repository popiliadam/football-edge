"""`history/store.py` sahte bağlantıyla; `0006_history.sql` metin üzerinden (mevcut desen)."""

from __future__ import annotations

import gzip
import hashlib
import re
from pathlib import Path

import pytest

from football_edge.collector import ContractViolation
from football_edge.history import store
from football_edge.history.store import CachedFile, load_files, log_fetch, save_file
from tests.fake_hist_db import FakeHistDb, at

MIGRATION = Path(__file__).resolve().parent.parent / "db/migrations/0006_history.sql"
PATH = "/mmz4281/2526/E0.csv"
CONTENT = b"Div,Date\r\nE0,16/08/2025\r\n"


def _save(db: FakeHistDb, content: bytes = CONTENT, minute: int = 0) -> bool:
    return save_file(
        db,
        path=PATH,
        content=content,
        fetched_at=at(minute),
        last_modified="Sun, 24 May 2026 20:00:00 GMT",
        row_count=380,
    )


def test_save_file_stores_gzip_content_with_the_sha_and_size_of_the_plain_bytes() -> None:
    db = FakeHistDb()

    assert _save(db) is True

    row = db.files[PATH]
    assert row["sha256"] == hashlib.sha256(CONTENT).hexdigest()
    assert row["byte_size"] == len(CONTENT)
    assert gzip.decompress(row["content"]) == CONTENT
    assert row["content"] != CONTENT, "içerik sıkıştırılmadan yazılmış"
    assert (row["row_count"], row["fetched_at"]) == (380, at(0))
    assert row["http_last_modified"] == "Sun, 24 May 2026 20:00:00 GMT"


def test_the_same_content_is_not_rewritten_and_keeps_its_first_seen_time() -> None:
    db = FakeHistDb()
    _save(db, minute=0)
    writes = sum("INSERT INTO hist_files" in text for text in db.statements)

    assert _save(db, minute=5) is False

    assert sum("INSERT INTO hist_files" in text for text in db.statements) == writes
    assert db.files[PATH]["fetched_at"] == at(0)


def test_changed_content_replaces_the_cached_version() -> None:
    db = FakeHistDb()
    _save(db, minute=0)
    newer = CONTENT + b"E0,23/08/2025\r\n"

    assert _save(db, newer, minute=5) is True

    assert db.files[PATH]["sha256"] == hashlib.sha256(newer).hexdigest()
    assert db.files[PATH]["fetched_at"] == at(5)
    assert len(db.files) == 1


def _log(db: FakeHistDb, *, sha256: str | None, status: int | None, minute: int = 0) -> None:
    log_fetch(
        db,
        path=PATH,
        fetched_at=at(minute),
        sha256=sha256,
        http_status=status,
        rows_parsed=380 if sha256 else 0,
        rows_rejected=1 if sha256 else 0,
    )


def test_every_attempt_is_logged_and_a_failed_one_has_no_sha() -> None:
    db = FakeHistDb()

    _log(db, sha256="ab" * 32, status=200, minute=0)
    _log(db, sha256=None, status=None, minute=1)

    assert [(row["sha256"], row["http_status"], row["rows_parsed"]) for row in db.fetches] == [
        ("ab" * 32, 200, 380),
        (None, None, 0),
    ]


def test_the_store_leaves_the_commit_to_its_caller() -> None:
    """Dosya yazıldı ama günlük satırı düştüyse ikisi birlikte geri alınabilmeli: commit sync'in."""
    db = FakeHistDb()
    _save(db)
    _log(db, sha256=None, status=None)

    assert db.commits == 0


def test_load_files_returns_plain_bytes_for_cached_paths_only() -> None:
    db = FakeHistDb()
    _save(db)

    loaded = load_files(db, [PATH, "/new/BRA.csv"])

    assert dict(loaded) == {
        PATH: CachedFile(
            path=PATH,
            sha256=hashlib.sha256(CONTENT).hexdigest(),
            fetched_at=at(0),
            content=CONTENT,
        )
    }
    assert type(loaded[PATH].content) is bytes


def test_load_files_refuses_content_that_does_not_match_its_sha() -> None:
    db = FakeHistDb()
    _save(db)
    db.files[PATH] = {**db.files[PATH], "content": gzip.compress(b"kurcalanmis", mtime=0)}

    with pytest.raises(ContractViolation, match="sha256"):
        load_files(db, [PATH])


# ── 0006_history.sql ────────────────────────────────────────────────────────


def _columns(table: str) -> dict[str, str]:
    """Tablonun sütun adı → tanımı (satır içi `--` yorumu atılmış, küçük harf)."""
    sql = MIGRATION.read_text(encoding="utf-8")
    body = re.search(rf"create table if not exists {table} \((.*?)\n\);", sql, flags=re.S)
    assert body is not None, f"{table} tablosu 0006'da yok"
    lines = (line.split("--")[0].strip().rstrip(",") for line in body.group(1).splitlines())
    return {line.split()[0]: " ".join(line.split()[1:]).lower() for line in lines if line}


def test_hist_files_is_a_cache_keyed_by_path_with_not_null_content() -> None:
    columns = _columns("hist_files")

    assert list(columns) == [
        "path",
        "sha256",
        "fetched_at",
        "http_last_modified",
        "byte_size",
        "row_count",
        "content",
    ]
    assert columns["path"] == "text primary key"
    assert columns["content"] == "bytea not null"
    assert columns["http_last_modified"] == "text"
    for name in ("sha256", "fetched_at", "byte_size", "row_count"):
        assert "not null" in columns[name], name


def test_hist_fetches_allows_a_null_sha_and_status_for_failed_attempts() -> None:
    columns = _columns("hist_fetches")

    assert list(columns) == [
        "id",
        "path",
        "fetched_at",
        "sha256",
        "http_status",
        "rows_parsed",
        "rows_rejected",
    ]
    assert columns["id"] == "bigserial primary key"
    assert (columns["sha256"], columns["http_status"]) == ("text", "int")
    for name in ("path", "fetched_at", "rows_parsed", "rows_rejected"):
        assert "not null" in columns[name], name


def test_the_fetch_log_is_append_only_and_the_cache_is_not() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    triggers = re.findall(
        r"create trigger \w+\s+before update or delete on (\w+)\s+for each row execute "
        r"function forbid_ledger_mutation\(\);",
        sql,
    )

    assert triggers == ["hist_fetches"]
    # Satır tetikleyicisi TRUNCATE'i görmez; bu olmasa günlük tek komutla silinirdi (R110).
    truncates = re.findall(
        r"create trigger \w+\s+before truncate on (\w+)\s+for each statement execute "
        r"function forbid_ledger_mutation\(\);",
        sql,
    )
    assert truncates == ["hist_fetches"]
    assert "create or replace function forbid_ledger_mutation" not in sql, (
        "0001'deki yeniden yazıldı"
    )


def test_raw_content_tables_hide_their_rows_from_api_roles() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    for table in ("hist_files", "hist_fetches"):
        assert f"alter table {table} enable row level security;" in sql, table
    assert "create policy" not in sql, "politika API rollerine satır açar"
    assert "force row level security" not in sql, "FORCE sahibi de politikaya bağlar"


def test_the_store_writes_exactly_the_columns_the_migration_creates() -> None:
    """Taklit store'un SQL'ini tanır, migration şemayı kurar: ikisini bağlayan tek yer burası."""

    def listed(statement: str) -> list[str]:
        found = re.search(r"\(([^)]*)\)\s*VALUES", statement)
        assert found is not None
        return [name.strip() for name in found.group(1).split(",")]

    assert listed(store._UPSERT_FILE) == list(_columns("hist_files"))
    assert listed(store._INSERT_FETCH) == list(_columns("hist_fetches"))[1:]
