"""Şablon alt kümesinin sadakati (§4.4/4, rereview4 m1–m3): her kapıda, DB'siz.

Şablon (`site_tpl`) yalnız `TEMPLATE_MIGRATIONS`la kurulur; ATLANAN migration'lar sitenin
gördüğü dünyayı değiştirmemeli. "Dokunma" DEYİM HEDEFİYLE tanımlanır: hedefi `leagues`,
`matches` ya da `odds_snapshots` olan DDL/DML, site şemalarına ya da `public`e yetki, site
nesnesi, varsayılan yetki.
Adıyla izinli iki istisna deyim listesine TAKILMAZ; belge amaçlıdır: (1) `references matches(id)`
(0009, 0012) — iç RI tetikleyicileri yalnız `matches`in UPDATE/DELETE'inde ateşlenir, site yalnız
okur; (2) `revoke … on function ops.*` ve `on schema ops` (0003–0005, 0008, 0011) — `ops` şablonda
yoktur. Test bir KARA LİSTEDİR: listede olmayan deyimi ve çalışma anında dinamik SQL'i ölçmez.
"""

from __future__ import annotations

import re

import pytest

from tests.site_db import MIGRATIONS, SKIPPED_MIGRATIONS, TEMPLATE_MIGRATIONS
from tests.sql_text import statements

_TARGET = r'(?:public\.)?"?(?:leagues|matches|odds_snapshots)"?(?![\w])'
_SCHEMAS = r'"?(?:public|site|site_input|site_audit)"?(?![\w])'
_LIST = r'(?:[\w."]+\s*,\s*)*'
FORBIDDEN = {
    "alter table": rf"\balter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?{_TARGET}",
    "create trigger": (
        rf"\bcreate\s+(?:or\s+replace\s+)?(?:constraint\s+)?trigger\b[^;]*?\bon\s+{_TARGET}"
    ),
    "drop trigger/policy/rule": rf"\bdrop\s+(?:trigger|policy|rule)\b[^;]*?\bon\s+{_TARGET}",
    "drop index": r"\bdrop\s+index\b",
    "create policy": rf"\bcreate\s+policy\b[^;]*?\bon\s+{_TARGET}",
    "create index": rf"\bcreate\s+(?:unique\s+)?index\b[^;]*?\bon\s+(?:only\s+)?{_TARGET}",
    "create rule": rf"\bcreate\s+(?:or\s+replace\s+)?rule\b[^;]*?\bto\s+{_TARGET}",
    "grant/revoke on table": rf"\b(?:grant|revoke)\b[^;]*?\bon\s+(?:table\s+)?{_LIST}{_TARGET}",
    "grant/revoke on all in schema": (
        rf"\b(?:grant|revoke)\b[^;]*?\bon\s+all\s+\w+\s+in\s+schema\s+{_LIST}{_SCHEMAS}"
    ),
    "grant/revoke on schema": rf"\b(?:grant|revoke)\b[^;]*?\bon\s+schema\s+{_LIST}{_SCHEMAS}",
    "create schema site*": r'\bcreate\s+schema\s+(?:if\s+not\s+exists\s+)?"?site',
    "alter default privileges": r"\balter\s+default\s+privileges\b",
    "site object or role": r"\bsite(?:_input|_audit)?\.|\bsite_reader\b",
    "dml on target": (
        rf"\b(?:insert\s+into|update|delete\s+from|truncate(?:\s+table)?|copy)\s+(?:only\s+)?"
        rf"{_TARGET}"
    ),
}


def findings(sql: str) -> list[str]:
    return [
        name
        for text in statements(sql)
        for name, pattern in FORBIDDEN.items()
        if re.search(pattern, text)
    ]


def test_every_migration_is_in_exactly_one_list() -> None:
    """m3: yeni bir dosya ne şablona girer ne taranır hâlde sessiz kalmaz."""
    on_disk = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    listed = [*TEMPLATE_MIGRATIONS, *SKIPPED_MIGRATIONS]

    assert len(listed) == len(set(listed)), "bir dosya iki listede"
    assert sorted(listed) == on_disk, f"sınıflandırılmamış: {sorted(set(on_disk) - set(listed))}"


@pytest.mark.parametrize("name", SKIPPED_MIGRATIONS)
def test_a_skipped_migration_does_not_touch_what_the_site_reads(name: str) -> None:
    assert findings((MIGRATIONS / name).read_text(encoding="utf-8")) == [], name


@pytest.mark.parametrize(
    ("statement", "rule"),
    [
        ("grant select on matches to anon;", "grant/revoke on table"),
        ("grant select on public.matches to anon;", "grant/revoke on table"),
        ('grant select on hist_files, "matches" to anon;', "grant/revoke on table"),
        ("alter table odds_snapshots add column x int;", "alter table"),
        ("alter table if exists only public.leagues enable row level security;", "alter table"),
        (
            "create trigger t before insert on leagues for each row execute function f();",
            "create trigger",
        ),
        (
            "drop trigger if exists odds_snapshots_append_only on odds_snapshots;",
            "drop trigger/policy/rule",
        ),
        ("drop index if exists matches_commence_idx;", "drop index"),
        ("create unique index if not exists u on matches (id);", "create index"),
        ("create policy p on public.odds_snapshots for select using (true);", "create policy"),
        ("create rule r as on insert to leagues do instead nothing;", "create rule"),
        ("grant usage on schema ops, public to anon;", "grant/revoke on schema"),
        (
            "grant select on all tables in schema public to service_role;",
            "grant/revoke on all in schema",
        ),
        ("create schema if not exists site_input;", "create schema site*"),
        ("alter default privileges grant select on tables to anon;", "alter default privileges"),
        ("create or replace view site.extra as select 1;", "site object or role"),
        ("grant site_reader to anon;", "site object or role"),
        ("insert into leagues values ('x');", "dml on target"),
        ("do $$ begin update public.matches set home_team = 'x'; end $$;", "dml on target"),
    ],
)
def test_each_forbidden_form_is_caught(statement: str, rule: str) -> None:
    """m1–m2: nitelenmiş ad, tırnak, `if not exists`, `unique`, çoklu hedef, DO bloğu."""
    assert rule in findings(f"-- örnek\n{statement}\n")


@pytest.mark.parametrize(
    "statement",
    [
        "create table z (id bigint, match_id text references matches(id));",
        "create table z (league text references leagues(id));",
        "revoke all on function ops.dispatch_seal() from public, anon, authenticated;",
        "revoke all on schema ops from public;",
        "create trigger t before update on hist_fetches for each row execute function f();",
        "-- grant select on matches to anon;",
    ],
)
def test_the_documented_exceptions_and_comments_are_not_findings(statement: str) -> None:
    """İstisnalar belge amaçlıdır: `references` ve `ops` hedefli deyimler listeye takılmaz."""
    assert findings(statement) == []
