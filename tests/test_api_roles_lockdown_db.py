"""0013 (DEFERRED 12a, R90): API rollerinin kilidi, eski tablolarda RLS, TRUNCATE bekçisi.

Üç katman.
- METİN testleri migration dosyasını okur ve her kapıda koşar.
- KATALOG testleri `DATABASE_URL` varsa o veritabanını SALT OKUR (`set transaction read only`):
  yetkiler, RLS, varsayılan yetkiler, tetikleyiciler; `anon`/`authenticated` olarak SELECT reddi.
  Yoksa ADIYLA atlanır (`zincir` adımı gibi). 0013 uygulanmamış bir veritabanında KIRMIZIDIR.
- KUM HAVUZU testleri `SANDBOX_DATABASE_URL` varsa BOŞ bir Supabase kabında (supabase/postgres 17.6)
  0001–0013'ü TEK işlemde uygular, davranışı sınar ve işlemi GERİ ALIR. Hedefte `odds_snapshots`
  zaten varsa hiçbir şey uygulanmadan KIRMIZI verir: canlıya yanlışlıkla bağlanmanın kilidi.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from football_edge.db import connect

MIGRATIONS = Path(__file__).resolve().parent.parent / "db/migrations"
MIGRATION = MIGRATIONS / "0013_api_roles_lockdown.sql"
API_ROLES = ("anon", "authenticated")
OLD_TABLES = (
    "leagues",
    "matches",
    "odds_snapshots",
    "source_observations",
    "match_results",
    "entity_aliases",
)
APPEND_ONLY_OLD = ("odds_snapshots", "source_observations", "match_results")
LIVE_URL = "DATABASE" + "_URL"
SANDBOX_URL = "SANDBOX_DATABASE" + "_URL"
NO_DATABASE = f"{LIVE_URL} yok — 0013 gerçek veritabanında sınanmadı"
NO_SANDBOX = f"{SANDBOX_URL} yok — 0001–0013 boş bir Supabase kabında uygulanmadı"
TABLE_PRIVILEGES = "SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _statements() -> str:
    """Yorumsuz, tek boşluklu metin: yorumdaki bir örnek kuralı karşılamış sayılmasın."""
    lines = (line.split("--")[0] for line in _sql().splitlines())
    return " ".join(" ".join(lines).split())


# ── Metin: her kapıda ────────────────────────────────────────────────────────


def test_0013_enables_rls_on_the_six_old_tables_without_force_or_policy() -> None:
    sql = _statements()

    for table in OLD_TABLES:
        assert f"alter table {table} enable row level security;" in sql, table
    assert "create policy" not in sql, "politika API rollerine satır açar"
    assert "force row level security" not in sql, "FORCE sahibi de politikaya bağlar"


def test_0013_revokes_existing_and_default_privileges_from_the_api_roles() -> None:
    sql = _statements()

    for kind in ("tables", "sequences", "functions"):
        assert f"revoke all on all {kind} in schema public from anon, authenticated;" in sql
        assert (
            "alter default privileges for role postgres in schema public "
            f"revoke all on {kind} from anon, authenticated;"
        ) in sql, kind
    assert (
        "alter default privileges for role postgres revoke execute on functions from public;"
        in (sql)
    )
    assert "revoke execute on function public.forbid_ledger_mutation() from public;" in sql


def test_0013_does_not_touch_service_role_or_grant_anything() -> None:
    sql = _statements()

    assert "service_role" not in sql
    assert not re.search(r"\bgrant\b", sql), "kilit yalnız geri alır"


def test_0013_guards_truncate_on_the_old_append_only_tables() -> None:
    truncates = re.findall(
        r"create trigger (\w+) before truncate on (\w+) for each statement execute "
        r"function forbid_ledger_mutation\(\);",
        _statements(),
    )

    assert truncates == [(f"{table}_no_truncate", table) for table in APPEND_ONLY_OLD]


def test_0013_trigger_function_names_the_table_and_pins_search_path() -> None:
    found = re.search(
        r"create or replace function public\.forbid_ledger_mutation\(\) returns trigger "
        r"language plpgsql set search_path = '' as \$\$(.*?)\$\$;",
        _statements(),
    )

    assert found is not None
    assert "tg_table_name" in found.group(1)
    assert "odds_snapshots" not in found.group(1), "12a: mesaj her tabloda aynı adı söylüyordu"


# ── Ortak doğrulamalar: katalog ve kum havuzu aynı iddiayı sorar ─────────────


def _rows(cur: psycopg.Cursor[Any], sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    cur.execute(sql, params)
    return list(cur.fetchall())


def _public_relations(cur: psycopg.Cursor[Any], kinds: str) -> list[str]:
    return [
        name
        for (name,) in _rows(
            cur,
            "SELECT c.relname::text FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace "
            "AND c.relkind::text = ANY(%s) ORDER BY 1",
            (list(kinds),),
        )
    ]


def _assert_rls_on_every_public_table(cur: psycopg.Cursor[Any]) -> None:
    rows = _rows(
        cur,
        "SELECT relname::text, relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE relnamespace = 'public'::regnamespace AND relkind IN ('r', 'p')",
    )
    assert {name for name, _, _ in rows} >= set(OLD_TABLES)
    assert [name for name, rls, _ in rows if not rls] == [], "RLS kapalı tablo"
    assert [name for name, _, force in rows if force] == [], "FORCE sahibin yazımını bağlar"


def _assert_api_roles_hold_nothing(cur: psycopg.Cursor[Any]) -> None:
    # has_*_privilege PUBLIC'ten ve rol üyeliğinden gelen yetkiyi de sayar: ölçülen ETKİN yetkidir.
    for role in API_ROLES:
        held = _rows(
            cur,
            "SELECT c.relkind::text, c.relname::text FROM pg_class c "
            "WHERE c.relnamespace = 'public'::regnamespace AND ("
            "  (c.relkind IN ('r', 'p', 'v', 'm', 'f') AND has_table_privilege(%s, c.oid, %s))"
            "  OR (c.relkind = 'S' AND has_sequence_privilege(%s, c.oid, 'USAGE,SELECT,UPDATE'))"
            ") UNION ALL "
            "SELECT 'function', p.oid::regprocedure::text FROM pg_proc p "
            "WHERE p.pronamespace = 'public'::regnamespace "
            "AND has_function_privilege(%s, p.oid, 'EXECUTE') ORDER BY 1, 2",
            (role, TABLE_PRIVILEGES, role, role),
        )
        assert held == [], role


def _assert_default_privileges_closed(cur: psycopg.Cursor[Any]) -> None:
    # defaclnamespace = 0: şemadan bağımsız (genel) girdi. Genel girdi YOKSA Postgres'in hazır
    # varsayılanı geçerlidir ve o, fonksiyonlarda PUBLIC'e EXECUTE verir.
    entries = _rows(
        cur,
        "SELECT defaclnamespace = 0, defaclobjtype::text FROM pg_default_acl "
        "WHERE defaclrole = 'postgres'::regrole "
        "AND (defaclnamespace = 'public'::regnamespace OR defaclnamespace = 0)",
    )
    grants = _rows(
        cur,
        "SELECT d.defaclnamespace = 0, d.defaclobjtype::text, a.grantee::regrole::text "
        "FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) a "
        "WHERE d.defaclrole = 'postgres'::regrole "
        "AND (d.defaclnamespace = 'public'::regnamespace OR d.defaclnamespace = 0) "
        "AND (a.grantee = 0 OR a.grantee = ANY(ARRAY['anon', 'authenticated']::regrole[]))",
    )
    assert (True, "f") in entries, "postgres'in yeni fonksiyonları PUBLIC'e EXECUTE veriyor"
    assert grants == [], grants


def _assert_trigger_function_and_truncate_guards(cur: psycopg.Cursor[Any]) -> None:
    ((config, source),) = _rows(
        cur,
        "SELECT proconfig, prosrc FROM pg_proc "
        "WHERE oid = 'public.forbid_ledger_mutation()'::regprocedure",
    )
    assert config == ['search_path=""'], config
    assert "tg_table_name" in source
    # pg_trigger.tgtype bitleri: 1 ROW, 2 BEFORE, 32 TRUNCATE.
    guarded = _rows(
        cur,
        "SELECT c.relname::text FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE NOT t.tgisinternal AND t.tgenabled <> 'D' AND t.tgtype & 32 = 32 "
        "AND t.tgtype & 1 = 0 AND t.tgtype & 2 = 2 "
        "AND t.tgfoid = 'public.forbid_ledger_mutation()'::regprocedure",
    )
    assert {name for (name,) in guarded} >= set(APPEND_ONLY_OLD)


def _assert_api_roles_cannot_select(cur: psycopg.Cursor[Any]) -> None:
    for role in API_ROLES:
        for table in _public_relations(cur, "rp"):
            cur.execute("SAVEPOINT api_role")
            cur.execute(f"SET LOCAL ROLE {role}")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(f"SELECT 1 FROM public.{table} LIMIT 1")
            cur.execute("ROLLBACK TO SAVEPOINT api_role")


# ── Katalog: yalnız DATABASE_URL varken, yalnız OKUMA ────────────────────────

needs_database = pytest.mark.skipif(not os.getenv(LIVE_URL), reason=NO_DATABASE)


@pytest.fixture
def read_only_cursor() -> Iterator[psycopg.Cursor[Any]]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            yield cur
    finally:
        conn.rollback()
        conn.close()


@needs_database
def test_catalog_every_public_table_has_rls_without_force(
    read_only_cursor: psycopg.Cursor[Any],
) -> None:
    _assert_rls_on_every_public_table(read_only_cursor)


@needs_database
def test_catalog_api_roles_hold_no_privilege_in_public(
    read_only_cursor: psycopg.Cursor[Any],
) -> None:
    _assert_api_roles_hold_nothing(read_only_cursor)


@needs_database
def test_catalog_default_privileges_no_longer_open_new_objects(
    read_only_cursor: psycopg.Cursor[Any],
) -> None:
    _assert_default_privileges_closed(read_only_cursor)


@needs_database
def test_catalog_trigger_function_and_truncate_guards(
    read_only_cursor: psycopg.Cursor[Any],
) -> None:
    _assert_trigger_function_and_truncate_guards(read_only_cursor)


@needs_database
def test_catalog_api_roles_are_refused_select(read_only_cursor: psycopg.Cursor[Any]) -> None:
    _assert_api_roles_cannot_select(read_only_cursor)


# ── Kum havuzu: boş Supabase kabında 0001–0013, tek işlem, sonunda geri alınır ─

needs_sandbox = pytest.mark.skipif(not os.getenv(SANDBOX_URL), reason=NO_SANDBOX)


def _apply(cur: psycopg.Cursor[Any], path: Path) -> None:
    # Parametresiz execute çok ifadeli metni olduğu gibi gönderir; `%` ve `$$` yorumlanmaz.
    cur.execute(path.read_text(encoding="utf-8").encode())


@pytest.fixture(scope="module")
def sandbox() -> Iterator[psycopg.Cursor[Any]]:
    conn = connect(os.environ[SANDBOX_URL])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.odds_snapshots') IS NULL, current_user")
            empty, user = cur.fetchone() or (False, None)
            if not empty or user != "postgres":
                pytest.fail(f"kum havuzu boş değil ya da rol {user!r} — hiçbir şey uygulanmadı")
            for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql")):
                _apply(cur, path)
            yield cur
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def box(sandbox: psycopg.Cursor[Any]) -> Iterator[psycopg.Cursor[Any]]:
    sandbox.execute("SAVEPOINT test_case")
    try:
        yield sandbox
    finally:
        sandbox.execute("ROLLBACK TO SAVEPOINT test_case")


def _seed(cur: psycopg.Cursor[Any]) -> None:
    """Sahip (`postgres`) olarak eski altı tabloya birer satır: RLS sahibin yazımını durdurmaz."""
    cur.execute(
        "INSERT INTO leagues VALUES ('t6.1', 't6_key', 'Lig', 'TR', 'tr', 'tr', true);"
        "INSERT INTO matches (id, league_id, commence_time, home_team, away_team) "
        "VALUES ('t6-m1', 't6.1', now(), 'A', 'B');"
        "INSERT INTO odds_snapshots (match_id, observed_at, bookmaker, market, outcome, price, "
        "prev_hash, row_hash) VALUES ('t6-m1', now(), 'b', 'h2h', 'A', 1.9, 'g', 't6-h1');"
        "INSERT INTO source_observations (source_id, entity_kind, entity_key, observed_at, "
        "payload, content_hash) VALUES ('s', 'k', 'e', now(), '{}', 'c');"
        "INSERT INTO match_results VALUES ('t6-m1', now(), 1, 0, true);"
        "INSERT INTO entity_aliases VALUES ('s', 'team', 'a', 'A', 0.9, now());"
    )


@needs_sandbox
def test_sandbox_catalog_matches_the_rules(box: psycopg.Cursor[Any]) -> None:
    _assert_rls_on_every_public_table(box)
    _assert_api_roles_hold_nothing(box)
    _assert_default_privileges_closed(box)
    _assert_trigger_function_and_truncate_guards(box)


@needs_sandbox
def test_sandbox_owner_writes_and_api_roles_are_refused(box: psycopg.Cursor[Any]) -> None:
    _seed(box)
    counts = [_rows(box, f"SELECT count(*) FROM {table}")[0][0] for table in OLD_TABLES]
    assert counts == [1] * len(OLD_TABLES), "sahip yazamadı ya da okuyamadı"

    _assert_api_roles_cannot_select(box)
    for role in API_ROLES:
        for table in _public_relations(box, "rp"):
            box.execute("SAVEPOINT api_insert")
            box.execute(f"SET LOCAL ROLE {role}")
            # Yetki denetimi satır ve kısıttan önce koşar: DEFAULT VALUES yeter.
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                box.execute(f"INSERT INTO public.{table} DEFAULT VALUES")
            box.execute("ROLLBACK TO SAVEPOINT api_insert")


@needs_sandbox
@pytest.mark.parametrize("table", APPEND_ONLY_OLD)
def test_sandbox_owner_cannot_truncate_and_the_message_names_the_table(
    box: psycopg.Cursor[Any], table: str
) -> None:
    _seed(box)

    with pytest.raises(psycopg.errors.RaiseException) as truncate:
        box.execute(f"TRUNCATE {table}")
    box.execute("ROLLBACK TO SAVEPOINT test_case")
    _seed(box)
    with pytest.raises(psycopg.errors.RaiseException) as delete:
        box.execute(f"DELETE FROM {table}")

    assert str(truncate.value).startswith(f"{table} append-only bir defterdir; TRUNCATE")
    assert str(delete.value).startswith(f"{table} append-only bir defterdir; DELETE")


@needs_sandbox
def test_sandbox_truncate_cascade_from_matches_is_refused(box: psycopg.Cursor[Any]) -> None:
    _seed(box)

    with pytest.raises(psycopg.errors.RaiseException, match="append-only bir defterdir; TRUNCATE"):
        box.execute("TRUNCATE matches CASCADE")


@needs_sandbox
def test_sandbox_new_objects_do_not_open_to_the_api_roles(box: psycopg.Cursor[Any]) -> None:
    box.execute(
        "CREATE TABLE public.t6_new (id bigserial PRIMARY KEY);"
        "CREATE FUNCTION public.t6_new_fn() RETURNS int LANGUAGE sql AS 'select 1';"
    )

    _assert_api_roles_hold_nothing(box)
    assert _rows(box, "SELECT has_table_privilege('service_role', 't6_new', 'SELECT')") == [
        (True,)
    ], "service_role'e dokunulmaz"


@needs_sandbox
def test_sandbox_applying_0013_again_is_harmless(box: psycopg.Cursor[Any]) -> None:
    _apply(box, MIGRATION)
    _apply(box, MIGRATION)

    _assert_rls_on_every_public_table(box)
    _assert_api_roles_hold_nothing(box)
    _assert_trigger_function_and_truncate_guards(box)


@needs_sandbox
def test_sandbox_dispatch_path_survives_the_lockdown(box: psycopg.Cursor[Any]) -> None:
    """pg_cron işi `postgres` olarak vault'u okur, pg_net kuyruğuna yazar. İşlem geri alınır:
    kuyruk satırı commit edilmediği için pg_net işçisi onu hiç görmez, istek gitmez."""
    box.execute("SELECT vault.create_secret('t6-sahte', 'github_seal_dispatch')")
    ((request_id,),) = _rows(box, "SELECT ops.dispatch_seal()")
    jobs = _rows(box, "SELECT DISTINCT username FROM cron.job")

    assert isinstance(request_id, int)
    assert jobs == [("postgres",)]
