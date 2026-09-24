"""0014 gerçek Postgres'te (§4.4/2): katalog tam sırada, davranış şablonun kopyasında.

Yalnız atılabilir yerel kapta koşar (`tests/site_db.py`): `scripts/sandbox_db.sh up` ve
`scripts/sandbox_db.sh test tests/test_site_views_db.py`. Değişken yoksa yerelde SKIP, CI'da FAIL.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from football_edge.site.contract import FORBIDDEN_KEYS, PUBLIC_FLOOR, RECORD_COLUMNS
from football_edge.site.schema import property_names
from tests.site_db import as_reader, full_sequence, site_cluster, site_db

pytestmark = pytest.mark.sitedb

REPO = Path(__file__).resolve().parent.parent
SCHEMAS = ("site", "site_input", "site_audit")
API_ROLES = ("anon", "authenticated", "service_role")
BASE_TABLES = {"public.leagues", "public.matches", "public.odds_snapshots"}


def _rows(cur: psycopg.Cursor[Any], query: str, params: tuple[Any, ...] = ()) -> list[Any]:
    cur.execute(query, params)
    return list(cur.fetchall())


QUALIFIED = "n.nspname || '.' || c.relname"
FROM_CLASS = "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"


def _views(cur: psycopg.Cursor[Any]) -> list[tuple[int, str]]:
    return [
        (oid, name)
        for oid, name in _rows(
            cur,
            f"SELECT c.oid::int, {QUALIFIED} {FROM_CLASS} "
            "WHERE n.nspname = ANY(%s) AND c.relkind = 'v' ORDER BY 2",
            (list(SCHEMAS),),
        )
    ]


def closure(cur: psycopg.Cursor[Any]) -> tuple[dict[str, str], set[str]]:
    """Görünümlerin `pg_depend` kapanışı: (ilişki → relkind, fonksiyonlar).

    Görünümün bağımlılığı kuralındadır (`pg_rewrite`); fonksiyonun gövde bağımlılığı `BEGIN ATOMIC`
    ile kaydedilir. Sabitlenmiş (`pg_catalog`) nesneler `pg_depend`e yazılmaz.
    """
    relations: dict[str, str] = {}
    functions: set[str] = set()
    pending = [("r", oid) for oid, _ in _views(cur)]
    seen: set[tuple[str, int]] = set()
    while pending:
        kind, oid = pending.pop()
        if (kind, oid) in seen:
            continue
        seen.add((kind, oid))
        if kind == "r":
            ((name, relkind),) = _rows(
                cur, f"SELECT {QUALIFIED}, c.relkind::text {FROM_CLASS} WHERE c.oid = %s", (oid,)
            )
            relations[name] = relkind
            deps = _rows(
                cur,
                "SELECT d.refclassid::regclass::text, d.refobjid::int FROM pg_rewrite r "
                "JOIN pg_depend d ON d.classid = 'pg_rewrite'::regclass AND d.objid = r.oid "
                "WHERE r.ev_class = %s AND d.refobjid <> %s "
                "AND d.refclassid IN ('pg_class'::regclass, 'pg_proc'::regclass)",
                (oid, oid),
            )
        else:
            ((name,),) = _rows(cur, "SELECT %s::oid::regprocedure::text", (oid,))
            functions.add(name)
            deps = _rows(
                cur,
                "SELECT refclassid::regclass::text, refobjid::int FROM pg_depend "
                "WHERE classid = 'pg_proc'::regclass AND objid = %s "
                "AND refclassid IN ('pg_class'::regclass, 'pg_proc'::regclass)",
                (oid,),
            )
        pending.extend(("r" if table == "pg_class" else "p", ref) for table, ref in deps)
    return relations, functions


# ── (i) tam sıra, postgres veritabanında, geri alınan işlem ──────────────────────────────────


@pytest.mark.leakage
def test_the_views_depend_on_exactly_the_three_ledger_tables_and_the_floor(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    """H1a: temel tablolar = {leagues, matches, odds_snapshots}; fonksiyonlar ⊆ {public_floor}."""
    relations, functions = closure(full_sequence)
    tables = {name for name, kind in relations.items() if kind == "r"}
    others = {name for name, kind in relations.items() if kind != "r"}

    assert tables == BASE_TABLES
    assert all(name.split(".")[0] in SCHEMAS for name in others), sorted(others)
    assert functions <= {"site.public_floor()"}, sorted(functions)


@pytest.mark.leakage
def test_the_floor_is_the_python_floor(full_sequence: psycopg.Cursor[Any]) -> None:
    assert _rows(full_sequence, "SELECT site.public_floor()") == [(PUBLIC_FLOOR,)]


def test_everything_is_owned_by_postgres_and_no_view_is_invoker(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    """§4.2: görünüm sahibi = tablo sahibi = postgres; `security_barrier` var, `invoker` yok."""
    owners = _rows(
        full_sequence,
        f"SELECT {QUALIFIED}, pg_get_userbyid(c.relowner), c.reloptions {FROM_CLASS} "
        f"WHERE (n.nspname = ANY(%s) AND c.relkind = 'v') OR {QUALIFIED} = ANY(%s) ORDER BY 1",
        (list(SCHEMAS), sorted(BASE_TABLES)),
    )
    ((floor_owner,),) = _rows(
        full_sequence,
        "SELECT pg_get_userbyid(proowner) FROM pg_proc "
        "WHERE oid = 'site.public_floor()'::regprocedure",
    )

    assert len(owners) == 6 + 3
    assert {owner for _, owner, _ in owners} == {"postgres"} and floor_owner == "postgres"
    for name, _, options in owners:
        if name not in BASE_TABLES:
            assert "security_barrier=true" in (options or []), name
            assert not any(o.startswith("security_invoker") for o in options or []), name


def test_api_roles_get_nothing_in_the_site_schemas(full_sequence: psycopg.Cursor[Any]) -> None:
    for role in API_ROLES:
        for schema in SCHEMAS:
            assert _rows(
                full_sequence, "SELECT has_schema_privilege(%s, %s, 'USAGE')", (role, schema)
            ) == [(False,)], (role, schema)
        for _, view in _views(full_sequence):
            assert _rows(
                full_sequence, "SELECT has_table_privilege(%s, %s, 'SELECT')", (role, view)
            ) == [(False,)], (role, view)
        assert _rows(
            full_sequence,
            "SELECT has_function_privilege(%s, 'site.public_floor()', 'EXECUTE')",
            (role,),
        ) == [(False,)], role


def test_site_reader_holds_no_table_privilege_and_cannot_log_in(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    held = _rows(
        full_sequence,
        f"SELECT {QUALIFIED} {FROM_CLASS} WHERE c.relkind IN ('r', 'p') AND n.nspname = 'public' "
        "AND has_table_privilege('site_reader', c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')",
    )
    ((login, bypass, inherit),) = _rows(
        full_sequence,
        "SELECT rolcanlogin, rolbypassrls, rolinherit FROM pg_roles WHERE rolname = 'site_reader'",
    )
    settings = _rows(
        full_sequence,
        "SELECT unnest(setconfig) FROM pg_db_role_setting "
        "WHERE setrole = 'site_reader'::regrole AND setdatabase = 0 ORDER BY 1",
    )

    assert held == []
    assert (login, bypass, inherit) == (False, False, False)
    assert settings == [("default_transaction_read_only=on",), ("statement_timeout=30s",)]


def _record_columns(cur: psycopg.Cursor[Any]) -> list[tuple[str, str]]:
    return [
        (name, kind)
        for name, kind in _rows(
            cur,
            "SELECT attname::text, format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = 'site.record'::regclass AND attnum > 0 AND NOT attisdropped "
            "ORDER BY attnum",
        )
    ]


def test_the_record_view_has_the_contract_columns_and_no_rows(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    assert _record_columns(full_sequence) == list(RECORD_COLUMNS)
    assert _rows(full_sequence, "SELECT count(*) FROM site.record") == [(0,)]


@pytest.mark.parametrize(
    "replacement",
    [
        "null::bigint as publication_no",  # ad değişti
        "null::text as publication_id",  # tip değişti
    ],
)
def test_replacing_the_record_view_cannot_rename_or_retype(
    full_sequence: psycopg.Cursor[Any], replacement: str
) -> None:
    """B5: Postgres ad/tip değişikliğini reddeder (vaka 1)."""
    rest = ", ".join(f"null::{kind} as {name}" for name, kind in RECORD_COLUMNS[1:])
    full_sequence.execute("SAVEPOINT replace_record")
    with pytest.raises(psycopg.errors.InvalidTableDefinition):
        full_sequence.execute(
            f"CREATE OR REPLACE VIEW site.record AS SELECT {replacement}, {rest} WHERE false"
        )
    full_sequence.execute("ROLLBACK TO SAVEPOINT replace_record")


def test_appending_a_record_column_is_accepted_by_postgres_but_red_here(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    """B5 vaka 2: sona kolon eklemeye Postgres izin verir; koruma kolon listesi testinden gelir."""
    columns = ", ".join(f"null::{kind} as {name}" for name, kind in RECORD_COLUMNS)
    full_sequence.execute("SAVEPOINT grow_record")
    full_sequence.execute(
        f"CREATE OR REPLACE VIEW site.record AS SELECT {columns}, null::text AS extra WHERE false"
    )
    grown = _record_columns(full_sequence)
    full_sequence.execute("ROLLBACK TO SAVEPOINT grow_record")

    assert grown != list(RECORD_COLUMNS)
    assert grown[: len(RECORD_COLUMNS)] == list(RECORD_COLUMNS)


def test_the_forbidden_key_set_is_the_catalog_difference(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    """§4.3: (site_input ∪ site_audit kolonları) − (site kolonları ∪ şemanın anahtarları)."""

    def columns(schemas: tuple[str, ...]) -> set[str]:
        return {
            name
            for (name,) in _rows(
                full_sequence,
                f"SELECT a.attname::text {FROM_CLASS} JOIN pg_attribute a ON a.attrelid = c.oid "
                "WHERE n.nspname = ANY(%s) AND c.relkind = 'v' AND a.attnum > 0 "
                "AND NOT a.attisdropped",
                (list(schemas),),
            )
        }

    schema = json.loads((REPO / "web/contract/snapshot.schema.json").read_text(encoding="utf-8"))
    derived = columns(("site_input", "site_audit")) - (columns(("site",)) | property_names(schema))

    assert derived and derived == FORBIDDEN_KEYS


def test_applying_0014_twice_is_harmless(full_sequence: psycopg.Cursor[Any]) -> None:
    """Rol ve nesneler idempotent: önceki oturumdan kalan `site_reader` hata vermez (n2)."""
    full_sequence.execute("SAVEPOINT again")
    full_sequence.execute((REPO / "db/migrations/0014_site_read.sql").read_text().encode())
    assert _record_columns(full_sequence) == list(RECORD_COLUMNS)
    full_sequence.execute("ROLLBACK TO SAVEPOINT again")


# ── (ii) davranış, şablonun kopyasında ───────────────────────────────────────────────────────

ACTIVE, PASSIVE = "tst.1", "tst.9"
HOLDOUT = ("m-holdout", "2026-01-15T12:00:00Z")
EDGE = ("m-edge", "2026-07-01T23:59:59.999999Z")
FLOOR = ("m-floor", "2026-07-02T00:00:00Z")
LIVE = ("m-live", "2026-09-20T18:00:00Z")
ASLEEP = ("m-passive", "2026-09-21T18:00:00Z")


@pytest.fixture(scope="module")
def seeded(site_db: str) -> Iterator[psycopg.Cursor[Any]]:
    """Sahip (`postgres`) olarak zincirsiz tohumlar: bu testler zincir değil süzgeç sınar."""
    conn = psycopg.connect(site_db)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO leagues VALUES (%s, 'k1', 'Deneme Ligi', 'Testland', 'tr', 'TR', true),"
            " (%s, 'k9', 'Uyuyan Lig', 'Testland', 'tr', 'TR', false)",
            (ACTIVE, PASSIVE),
        )
        for match_id, kickoff in (HOLDOUT, EDGE, FLOOR, LIVE, ASLEEP):
            league = PASSIVE if match_id == ASLEEP[0] else ACTIVE
            cur.execute(
                "INSERT INTO matches (id, league_id, commence_time, home_team, away_team) "
                "VALUES (%s, %s, %s, 'Ev', 'Dep')",
                (match_id, league, kickoff),
            )
            for book in ("kitap-b", "kitap-a"):
                cur.execute(
                    "INSERT INTO odds_snapshots (match_id, observed_at, bookmaker, market, "
                    "outcome, price, prev_hash, row_hash) "
                    "VALUES (%s, '2026-06-30T10:00:00Z', %s, 'h2h', 'Ev', 2.0, 'g', %s)",
                    (match_id, book, f"{match_id}-{book}"),
                )
        conn.commit()
        yield cur
    conn.rollback()
    conn.close()


@pytest.mark.leakage
def test_the_floor_filters_holdout_and_its_neighbour_but_keeps_the_floor(
    seeded: psycopg.Cursor[Any],
) -> None:
    """H1b: 2026-01-15 ve 2026-07-01T23:59:59.999999Z → 0 satır; 2026-07-02T00:00Z → 1 satır."""
    with as_reader(seeded) as cur:
        matches = {row[0] for row in _rows(cur, "SELECT id FROM site.matches")}
        quoted = {
            row[0] for row in _rows(cur, "SELECT DISTINCT match_id FROM site_input.h2h_quotes")
        }

    assert matches == {FLOOR[0], LIVE[0]}
    assert quoted == {FLOOR[0], LIVE[0]}


def test_site_reader_sees_rows_through_the_views(seeded: psycopg.Cursor[Any]) -> None:
    """§4.2 bekçi 2 + `grant execute` yük taşır: 0 satır da kırmızıdır."""
    with as_reader(seeded) as cur:
        (count,) = _rows(cur, "SELECT count(*) FROM site.matches")[0]
        leagues = _rows(cur, "SELECT id FROM site.leagues")
        (head,) = _rows(cur, "SELECT rows, last_id FROM site.ledger_head")

    assert count > 0
    assert leagues == [(ACTIVE,)], "pasif lig düşmeli"
    assert head == (10, 10)


def test_book_key_is_the_book_order_within_a_round_and_no_book_name_leaks(
    seeded: psycopg.Cursor[Any],
) -> None:
    with as_reader(seeded) as cur:
        keys = _rows(
            cur,
            "SELECT book_key, ledger_id FROM site_input.h2h_quotes WHERE match_id = %s "
            "ORDER BY ledger_id",
            (LIVE[0],),
        )
        columns = [d.name for d in cur.description or ()]

    # kitap-b önce eklendi (küçük ledger_id) ama sırada kitap-a'dan sonra gelir.
    assert [key for key, _ in keys] == [2, 1]
    assert "bookmaker" not in columns


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT 1 FROM public.odds_snapshots LIMIT 1",
        "SELECT 1 FROM public.matches LIMIT 1",
        "INSERT INTO public.odds_snapshots DEFAULT VALUES",
        "INSERT INTO site.leagues (id, name, country) VALUES ('x', 'x', 'x')",
    ],
)
def test_site_reader_cannot_touch_a_table_or_write_through_a_view(
    seeded: psycopg.Cursor[Any], statement: str
) -> None:
    """Sınır yetkidir: `default_transaction_read_only` kaza önleyicidir, SET ROLE'de etkin değil."""
    with as_reader(seeded) as cur, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cur.execute(statement)
