"""0012 (Faz 4 tasarımı §4): haber ve Jev tabloları append-only, tekil anahtarlı, RLS'li.

İki katman. METİN testleri migration dosyasını okur ve her kapıda koşar. KATALOG testleri
`DATABASE_URL` varsa gerçek veritabanının `pg_catalog`unu OKUR — hiçbir tabloya satır yazmaz
(append-only tablolara deneme satırı yazılmaz, plan Global Constraints); yoksa ADIYLA atlanır
(`zincir` adımı gibi). 0012 uygulanmamış bir veritabanında katalog testleri KIRMIZIDIR.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest

from football_edge.db import connect

MIGRATION = Path(__file__).resolve().parent.parent / "db/migrations/0012_jev_features.sql"
TABLES = ("news_items", "jev_item_answers", "jev_match_answers", "jev_spend")
NO_DATABASE = "DATABASE_URL yok — 0012 gerçek veritabanında sınanmadı"
COLUMN_TYPES = r"(bigserial|bigint|text|timestamptz|double precision|numeric|jsonb|integer)"

EXPECTED_COLUMNS = {
    "news_items": [
        "id",
        "source_id",
        "lang",
        "title",
        "body",
        "url",
        "published_at_claimed",
        "first_seen_at",
        "available_at",
        "availability_basis",
        "content_hash",
        "recorded_at",
    ],
    "jev_item_answers": [
        "id",
        "item_id",
        "prompt_version",
        "question_id",
        "choice",
        "probabilities",
        "confidence",
        "match_id",
        "side",
        "cluster_id",
        "jev_model",
        "asked_at",
        "cost_usd",
        "recorded_at",
    ],
    "jev_match_answers": [
        "id",
        "match_id",
        "decided_at",
        "prompt_version",
        "question_id",
        "variant",
        "item_set_hash",
        "choice",
        "probabilities",
        "confidence",
        "jev_model",
        "asked_at",
        "cost_usd",
        "recorded_at",
    ],
    "jev_spend": [
        "id",
        "spent_at",
        "kind",
        "cost_usd",
        "cost_basis",
        "input_tokens",
        "output_tokens",
        "recorded_at",
    ],
}
EXPECTED_UNIQUE = {
    "news_items": ["source_id", "content_hash"],
    "jev_item_answers": ["item_id", "prompt_version", "question_id"],
    "jev_match_answers": ["match_id", "decided_at", "prompt_version", "question_id", "variant"],
}
EXPECTED_FOREIGN_KEYS = {
    ("jev_item_answers", "item_id", "news_items"),
    ("jev_item_answers", "match_id", "matches"),
    ("jev_match_answers", "match_id", "matches"),
}


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _body(table: str) -> str:
    found = re.search(rf"create table if not exists {table} \((.*?)\n\);", _sql(), flags=re.S)
    assert found is not None, f"{table} tablosu 0012'de yok"
    return found.group(1)


def _columns(table: str) -> dict[str, str]:
    columns: dict[str, str] = {}
    for raw in _body(table).splitlines():
        line = raw.split("--")[0].strip().rstrip(",")
        found = re.match(rf"([a-z_]+)\s+{COLUMN_TYPES}\b(.*)", line)
        if found is not None:
            columns[found.group(1)] = f"{found.group(2)}{found.group(3)}".strip()
    return columns


# ── Metin: her kapıda ────────────────────────────────────────────────────────


def test_0012_creates_the_four_tables_with_the_spec_columns() -> None:
    for table, expected in EXPECTED_COLUMNS.items():
        assert list(_columns(table)) == expected, table


def test_0012_unique_keys_are_the_spec_keys() -> None:
    for table, expected in EXPECTED_UNIQUE.items():
        keys = re.findall(r"^\s*unique \(([^)]*)\)", _body(table), flags=re.M)
        assert [[part.strip() for part in key.split(",")] for key in keys] == [expected], table
    assert "unique" not in _body("jev_spend"), "jev_spend'in anahtarı yalnız id"


def test_0012_foreign_keys_bind_answers_to_news_and_matches() -> None:
    found = {
        (table, column, target)
        for table in TABLES
        for column, definition in _columns(table).items()
        for target in re.findall(r"references (\w+)\(id\)", definition)
    }

    assert found == EXPECTED_FOREIGN_KEYS
    assert "not null" in _columns("jev_item_answers")["item_id"]
    assert "not null" not in _columns("jev_item_answers")["match_id"], "eşleşmeyen haber de sorulur"
    assert "not null" in _columns("jev_match_answers")["match_id"]


def test_0012_enumerations_are_closed_by_check_constraints() -> None:
    news = _columns("news_items")
    match_answers = _columns("jev_match_answers")

    assert "availability_basis in ('observed', 'archive_claimed')" in news["availability_basis"]
    assert "variant in ('real', 'blank', 'shuffled')" in match_answers["variant"]
    assert "cost_basis in ('reported', 'estimated')" in _columns("jev_spend")["cost_basis"]
    assert "side in ('home', 'away', 'both')" in _columns("jev_item_answers")["side"]


def test_0012_every_table_is_append_only_including_truncate() -> None:
    sql = _sql()
    rows = re.findall(
        r"create trigger \w+\s+before update or delete on (\w+)\s+for each row execute "
        r"function forbid_ledger_mutation\(\);",
        sql,
    )
    truncates = re.findall(
        r"create trigger \w+\s+before truncate on (\w+)\s+for each statement execute "
        r"function forbid_ledger_mutation\(\);",
        sql,
    )

    assert rows == list(TABLES)
    assert truncates == list(TABLES)
    assert "create or replace function forbid_ledger_mutation" not in sql, "0001'in işi"


def test_0012_every_table_has_rls_and_no_policy() -> None:
    sql = _sql()

    for table in TABLES:
        assert f"alter table {table} enable row level security;" in sql, table
    assert "create policy" not in sql, "politika API rollerine satır açar"
    assert "force row level security" not in sql, "FORCE sahibi de politikaya bağlar"


# ── Katalog: yalnız DATABASE_URL varken, yalnız OKUMA ────────────────────────


def _query(sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    with connect() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())
        finally:
            conn.rollback()


needs_database = pytest.mark.skipif(not os.getenv("DATABASE" + "_URL"), reason=NO_DATABASE)


@needs_database
def test_catalog_tables_exist_with_row_level_security() -> None:
    rows = _query(
        """
        SELECT c.relname::text, c.relrowsecurity
        FROM pg_class c
        WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
          AND c.relname::text = ANY(%s)
        """,
        (list(TABLES),),
    )

    assert dict(rows) == dict.fromkeys(TABLES, True)


@needs_database
def test_catalog_every_table_has_row_and_truncate_ledger_triggers() -> None:
    # pg_trigger.tgtype bitleri: 1 ROW, 2 BEFORE, 8 DELETE, 16 UPDATE, 32 TRUNCATE.
    rows = _query(
        """
        SELECT c.relname::text, t.tgtype
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_proc p ON p.oid = t.tgfoid
        WHERE NOT t.tgisinternal AND t.tgenabled <> 'D'
          AND p.proname = 'forbid_ledger_mutation'
          AND c.relnamespace = 'public'::regnamespace AND c.relname::text = ANY(%s)
        """,
        (list(TABLES),),
    )

    for table in TABLES:
        kinds = [tgtype for name, tgtype in rows if name == table]
        assert any(k & 1 and k & 2 and k & 8 and k & 16 for k in kinds), f"{table}: satır"
        assert any(not k & 1 and k & 2 and k & 32 for k in kinds), f"{table}: truncate"


@needs_database
def test_catalog_unique_keys_match_the_spec() -> None:
    rows = _query(
        """
        SELECT c.relname::text, array_agg(a.attname::text ORDER BY k.ord)
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
        WHERE con.contype = 'u' AND c.relname::text = ANY(%s)
          AND c.relnamespace = 'public'::regnamespace
        GROUP BY c.relname, con.oid
        """,
        (list(TABLES),),
    )

    assert sorted((table, list(columns)) for table, columns in rows) == sorted(
        EXPECTED_UNIQUE.items()
    )


@needs_database
def test_catalog_foreign_keys_and_checks_match_the_migration() -> None:
    foreign = _query(
        """
        SELECT c.relname::text, a.attname::text, f.relname::text
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_class f ON f.oid = con.confrelid
        JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = con.conkey[1]
        WHERE con.contype = 'f' AND c.relname::text = ANY(%s)
          AND c.relnamespace = 'public'::regnamespace
        """,
        (list(TABLES),),
    )
    checks = _query(
        """
        SELECT c.relname::text, pg_get_constraintdef(con.oid)
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        WHERE con.contype = 'c' AND c.relname::text = ANY(%s)
          AND c.relnamespace = 'public'::regnamespace
        """,
        (list(TABLES),),
    )

    assert set(foreign) == EXPECTED_FOREIGN_KEYS
    defs = {table: " ".join(d for t, d in checks if t == table) for table in TABLES}
    for value in ("'real'", "'blank'", "'shuffled'"):
        assert value in defs["jev_match_answers"], value
    assert "'archive_claimed'" in defs["news_items"]
    assert "(available_at >= first_seen_at)" in defs["news_items"]
    default = _query(
        """
        SELECT pg_get_expr(d.adbin, d.adrelid), a.attnotnull
        FROM pg_attrdef d
        JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum
        WHERE d.adrelid = 'public.news_items'::regclass AND a.attname = 'first_seen_at'
        """
    )
    assert default == [("now()", True)], "first_seen_at veritabanı saatiyle ve boş olamaz dolmalı"
    for table in ("jev_item_answers", "jev_match_answers", "jev_spend"):
        assert "'Infinity'" in defs[table], table


# ── Review Focus ─────────────────────────────────────────────────────────────


def test_review_focus_cost_columns_reject_nan_and_infinity() -> None:
    """numeric'te NaN `>= 0`ı geçer; ay toplamına girerse tavan karşılaştırması hep yanlış olur."""
    for table in ("jev_item_answers", "jev_match_answers", "jev_spend"):
        assert "cost_usd >= 0 and cost_usd < 'Infinity'" in _columns(table)["cost_usd"], table


@pytest.mark.leakage
def test_review_focus_archive_news_cannot_lack_its_claimed_publication_time() -> None:
    """Arşiv haberinin `available_at`i iddiadan türer; iddiasız satır sızıntı denetimini körler."""
    body = " ".join(_body("news_items").split())

    assert (
        "check ( availability_basis <> 'archive_claimed' or (published_at_claimed is not null "
        "and available_at >= published_at_claimed) )"
    ) in body


@pytest.mark.leakage
def test_review_focus_live_news_is_never_available_before_we_first_saw_it() -> None:
    """R172: yayıncının `observed_at`i bizim saatimiz değil; canlı haber ilk görüşten önce yoktu."""
    body = " ".join(_body("news_items").split())

    assert _columns("news_items")["first_seen_at"] == "timestamptz not null default now()"
    assert (
        "check ( availability_basis <> 'observed' or ( available_at >= first_seen_at and "
        "(published_at_claimed is null or available_at >= published_at_claimed) ) )"
    ) in body
