"""0014 METNİ (§4.4/1): her kapıda, DB'siz. Yorumlar ayıklanır, yorumdaki kelime sayılmaz."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from football_edge.collect import _LEDGER_COLUMNS
from football_edge.site.contract import PUBLIC_FLOOR, RECORD_COLUMNS
from tests.sql_text import statements

MIGRATION = Path(__file__).resolve().parent.parent / "db/migrations/0014_site_read.sql"
VIEWS = (
    "site.leagues",
    "site.matches",
    "site.ledger_head",
    "site.record",
    "site_input.h2h_quotes",
    "site_audit.ledger_rows",
)
SOURCES = {
    "public.leagues",
    "public.matches",
    "public.odds_snapshots",
    "site.leagues",
    "site.matches",
}
# Görünüm başına beklenen süzgeç (§4.4/1): taban yalnız maç satırı taşıyan iki görünümde.
FILTERS = {
    "site.leagues": ("where l.active",),
    "site.matches": (
        "join site.leagues l on l.id = m.league_id",
        "where m.commence_time >= site.public_floor()",
    ),
    "site.ledger_head": (),
    "site.record": ("where false",),
    "site_input.h2h_quotes": ("join site.matches m on m.id = o.match_id", "where o.market = 'h2h'"),
    "site_audit.ledger_rows": (),
}
_TYPES = {"timestamptz": "timestamp with time zone"}
# §4.3: `site` şemasındaki her kolon yayımlanabilir; eklenen kolon AK6 onayı ister (ör. `sealed_at`
# alınmaz). Seçim listesi İFADE düzeyinde sabittir: yayımlanmayan kolon yayımlanan bir ad altında
# (`m.sealed_at::text as away_team`) da kırmızıdır. Tipler katalogda (`test_site_views_db.py`).
# `site.record` kolonları `RECORD_COLUMNS`la ayrıca sabitlenir.
SITE_SELECT = {
    "site.leagues": ("l.id", "l.name", "l.country"),
    "site.matches": ("m.id", "m.league_id", "m.commence_time", "m.home_team", "m.away_team"),
    "site.ledger_head": (
        "count(*)::bigint as rows",
        "coalesce(max(o.id), 0)::bigint as last_id",
        "coalesce( (select o2.row_hash from public.odds_snapshots o2 order by o2.id desc limit 1),"
        " repeat('0', 64) ) as head",
    ),
}


def _statements() -> list[str]:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def _views() -> dict[str, str]:
    found: dict[str, str] = {}
    for text in _statements():
        head = re.match(r"create or replace view ([\w.]+) with \(security_barrier\) as (.*)", text)
        if head is not None:
            found[head.group(1)] = head.group(2)
    return found


def _select_items(body: str) -> tuple[str, ...]:
    """`select … from` listesinin öğeleri: parantez içindeki virgül ve `from` sayılmaz."""
    items, current, depth, index = [], "", 0, len("select ")
    assert body.startswith("select "), body
    while index < len(body):
        char = body[index]
        depth += (char == "(") - (char == ")")
        if depth == 0 and body.startswith(" from ", index):
            break
        if depth == 0 and char == ",":
            items.append(current.strip())
            current = ""
        else:
            current += char
        index += 1
    items.append(current.strip())
    return tuple(items)


def test_0014_bounds_its_lock_wait_in_the_form_every_sender_honours() -> None:
    """DEFERRED 18f: `set local` autocommit gönderimde bağlamaz; `set … reset` her yerde bağlar."""
    assert (_statements()[0], _statements()[-1]) == (
        "set lock_timeout = '5s'",
        "reset lock_timeout",
    )


def test_every_view_is_created_with_security_barrier_and_none_is_invoker() -> None:
    """§4.2: `security_invoker` site_reader'a RLS uygular ve görünüm HATASIZ 0 satır döner."""
    assert sorted(_views()) == sorted(VIEWS)
    assert all("security_invoker" not in text for text in _statements())


def test_views_read_only_the_three_ledger_tables_or_other_site_views() -> None:
    """H1a (metin katmanı): görünümler yalnız leagues/matches/odds_snapshots'a dayanır."""
    for name, body in _views().items():
        sources = set(re.findall(r"\b(?:from|join) ([\w.]+)", body))
        assert sources <= SOURCES, f"{name}: {sorted(sources - SOURCES)}"


@pytest.mark.leakage
@pytest.mark.parametrize("view", VIEWS)
def test_each_view_carries_exactly_its_expected_filter(view: str) -> None:
    """Taban yalnız `site.matches`te yazılır; `site_input.h2h_quotes` onu join'le devralır."""
    body = _views()[view]

    for clause in FILTERS[view]:
        assert clause in body, f"{view}: {clause!r} yok"
    if "public_floor" in body:
        assert view == "site.matches", f"{view} tabanı kendisi süzmemeli"
    if not FILTERS[view]:
        assert " where " not in f" {body} ", f"{view} süzmemeli"


@pytest.mark.leakage
def test_the_floor_function_returns_the_python_floor_and_reads_no_table() -> None:
    (text,) = [
        s for s in _statements() if s.startswith("create or replace function site.public_floor")
    ]
    literal = PUBLIC_FLOOR.strftime("%Y-%m-%d %H:%M:%S+00")

    assert text == (
        "create or replace function site.public_floor() returns timestamptz language sql "
        f"immutable begin atomic select '{literal}'::timestamptz; end"
    )


def test_the_record_placeholder_is_where_false_with_the_contract_columns() -> None:
    """B5/H3c–d: gövde `where false`; kolon adları ve tipleri Python sabitiyle aynı sırada."""
    body = _views()["site.record"]
    columns = re.findall(r"null::([a-z ]+?) as (\w+)", body)

    assert body.endswith("where false")
    assert [(name, _TYPES.get(kind, kind)) for kind, name in columns] == list(RECORD_COLUMNS)


@pytest.mark.parametrize("view", sorted(SITE_SELECT))
def test_each_published_view_carries_exactly_its_columns(view: str) -> None:
    """I3: `site` = yayımlanabilir; seçim listesi ifade, ad ve sırayla sabit (`*` de kırmızı)."""
    assert _select_items(_views()[view]) == SITE_SELECT[view]


def test_the_audit_view_carries_id_plus_the_hashed_ledger_columns() -> None:
    """C1: `id` hash'i bozmaz (`payload_of` ayıklar); kolonlar zincir okuyucusunun sabitinden."""
    columns = re.findall(r"o\.(\w+)", _views()["site_audit.ledger_rows"].split(" from ")[0])

    assert tuple(columns) == ("id", *_LEDGER_COLUMNS)


def test_grants_go_only_to_site_reader_and_floor_execute_is_granted_explicitly() -> None:
    grants = [text for text in _statements() if text.startswith("grant ")]

    assert grants and all(text.endswith(" to site_reader") for text in grants)
    assert "grant execute on function site.public_floor() to site_reader" in grants
    assert (
        "revoke all on function site.public_floor() from public, anon, authenticated, service_role"
        in _statements()
    )
    assert all("site_reader" not in text for text in grants if " on " not in text)


def test_the_role_is_created_idempotently_without_login_or_password() -> None:
    """§4.2/AK18: parola ve oturum hakkı migration'da YOK; rol küme düzeyinde tekrar yaratılmaz."""
    text = " ".join(_statements())

    assert (
        "do $$ begin if not exists (select 1 from pg_roles where rolname = 'site_reader') "
        "then create role site_reader nologin noinherit; end if; end $$"
    ) in text
    assert re.search(r"\blogin\b", text) is None
    assert re.search(r"\bpassword\b", text) is None
    assert "alter role site_reader set default_transaction_read_only = on" in text
    assert "alter role site_reader set statement_timeout = '30s'" in text


def test_no_statement_names_a_table_outside_the_site_closure() -> None:
    names = set(re.findall(r"\bpublic\.(\w+)", " ".join(_statements())))

    assert names <= {"leagues", "matches", "odds_snapshots"}, sorted(names)
